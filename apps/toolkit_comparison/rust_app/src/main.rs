//! The bench supply panel of app.py, written in Rust with egui (a native GUI, no web view).
//!
//! Run:  cargo run --release      (from apps/toolkit_comparison/rust_app)
use eframe::egui;
use egui_plot::{Line, Plot};
use std::collections::VecDeque;
use std::time::{Duration, Instant};

const LOAD_OHMS: f64 = 8.0;
const TRIP_C: f64 = 85.0;
const RESET_C: f64 = 50.0;
const FANS: [&str; 3] = ["AUTO", "LOW", "HIGH"];
const SERIES: [(&str, f64); 3] = [("Voltage", 24.0), ("Current", 4.0), ("Temperature", 100.0)];

struct Panel {
    output: bool,
    vset: f64,
    fan: usize,
    v: f64,
    i: f64,
    t: f64,
    tripped: bool,
    message: String,
    history: [VecDeque<f64>; 3],
    last: Instant,
    steps: u64,
    noise: u64,
    bench: Bench,
}

impl Panel {
    fn new() -> Self {
        Self {
            output: false,
            vset: 12.0,
            fan: 0,
            v: 0.0,
            i: 0.0,
            t: 25.0,
            tripped: false,
            message: String::new(),
            history: Default::default(),
            last: Instant::now(),
            steps: 0,
            noise: 0x9E3779B97F4A7C15,
            bench: Bench::new(),
        }
    }

    /// Small noise source so the app needs no extra crate: roughly +/- 0.7 %.
    fn jitter(&mut self) -> f64 {
        self.noise ^= self.noise << 13;
        self.noise ^= self.noise >> 7;
        self.noise ^= self.noise << 17;
        ((self.noise % 2001) as f64 / 1000.0 - 1.0) * 0.007
    }

    fn step(&mut self, dt: f64) {
        let target = if self.output { self.vset } else { 0.0 };
        self.v += (target - self.v) * (dt / 0.15).min(1.0);
        self.i = if self.v > 0.01 { self.v / LOAD_OHMS * (1.0 + self.jitter()) } else { 0.0 };
        let airflow = match FANS[self.fan] {
            "LOW" => 0.3,
            "HIGH" => 1.0,
            _ => ((self.t - 40.0) / 20.0).clamp(0.2, 1.0),
        };
        self.t += (self.v * self.i * 0.9 - (self.t - 25.0) * (0.4 + 1.6 * airflow)) * dt / 6.0;
        if self.t >= TRIP_C && !self.tripped {
            self.tripped = true;
            self.output = false;
        }
        self.steps += 1;
        if self.steps % 5 == 0 {
            for (buf, value) in self.history.iter_mut().zip([self.v, self.i, self.t]) {
                buf.push_back(value);
                if buf.len() > 600 {
                    buf.pop_front();
                }
            }
        }
    }
}

impl eframe::App for Panel {
    fn logic(&mut self, ctx: &egui::Context, _frame: &mut eframe::Frame) {
        Bench::before_logic(self, ctx);
        while self.last.elapsed() >= Duration::from_millis(20) {
            self.last += Duration::from_millis(20);
            self.step(0.02);
        }
        ctx.request_repaint_after(Duration::from_millis(20));
    }

    fn ui(&mut self, ui: &mut egui::Ui, _frame: &mut eframe::Frame) {
        egui::CentralPanel::default().show(ui, |ui| {
            let hot = if self.t >= 80.0 {
                egui::Color32::RED
            } else if self.t >= 65.0 {
                egui::Color32::ORANGE
            } else {
                ui.visuals().text_color()
            };
            let normal = ui.visuals().text_color();
            let readouts = [
                ("Voltage", format!("{:.2}", self.v), "V", normal),
                ("Current", format!("{:.2}", self.i), "A", normal),
                ("Temperature", format!("{:.1}", self.t), "°C", hot),
            ];
            ui.columns(3, |cols| {
                for (col, (name, value, unit, color)) in cols.iter_mut().zip(readouts) {
                    col.group(|ui| {
                        ui.label(name);
                        ui.label(egui::RichText::new(value).monospace().size(28.0).color(color));
                        ui.label(unit);
                    });
                }
            });

            ui.horizontal(|ui| {
                ui.add_enabled(!self.tripped, egui::Checkbox::new(&mut self.output, "Output"));
                ui.label("Setpoint");
                ui.add(egui::Slider::new(&mut self.vset, 0.0..=24.0).suffix(" V"));
                ui.label("Fan");
                egui::ComboBox::from_id_salt("fan").selected_text(FANS[self.fan]).show_ui(ui, |ui| {
                    for (n, name) in FANS.iter().enumerate() {
                        ui.selectable_value(&mut self.fan, n, *name);
                    }
                });
                ui.label(if self.tripped { "FAULT" } else if self.output { "RUNNING" } else { "IDLE" });
                if ui.button("Reset Trip").clicked() {
                    if self.t > RESET_C {
                        self.message = format!("Board is still above {RESET_C} °C");
                    } else {
                        self.tripped = false;
                        self.message.clear();
                    }
                }
                ui.label(&self.message);
            });

            Plot::new("trend").allow_drag(false).allow_zoom(false).allow_scroll(false).include_y(0.0).include_y(100.0).show(ui, |plot| {
                for ((name, scale), data) in SERIES.iter().zip(&self.history) {
                    let points: Vec<[f64; 2]> = data.iter().enumerate().map(|(n, y)| [n as f64, y * 100.0 / scale]).collect();
                    plot.line(Line::new(*name, points));
                }
            });
        });
        self.bench.after_ui();
    }
}

fn main() -> eframe::Result {
    let options = eframe::NativeOptions {
        viewport: egui::ViewportBuilder::default().with_inner_size([900.0, 520.0]),
        ..Default::default()
    };
    eframe::run_native("Bench Supply", options, Box::new(|_cc| Ok(Box::new(Panel::new()))))
}

// --- bench: instrumentation for run.py (not part of the app, not counted as code)
struct Bench {
    secs: Option<f64>,
    start: Instant,
    frames: u64,
    asked: Option<Instant>,
    next_ping: Instant,
    lat: Vec<f64>,
}

impl Bench {
    fn new() -> Self {
        let secs = std::env::var("BENCH_SECS").ok().and_then(|s| s.parse().ok());
        Self { secs, start: Instant::now(), frames: 0, asked: None, next_ping: Instant::now(), lat: Vec::new() }
    }

    fn before_logic(panel: &mut Panel, ctx: &egui::Context) {
        let Some(secs) = panel.bench.secs else { return };
        if panel.bench.frames == 0 {
            (panel.output, panel.vset, panel.fan) = (true, 20.0, 2);
        }
        if let Some(t0) = panel.bench.asked.take() {
            panel.bench.lat.push(t0.elapsed().as_secs_f64() * 1000.0);
        }
        if Instant::now() >= panel.bench.next_ping {
            panel.bench.next_ping = Instant::now() + Duration::from_millis(200);
            panel.bench.asked = Some(Instant::now());
            ctx.request_repaint();
        }
        if panel.bench.start.elapsed().as_secs_f64() >= secs {
            let mut xs = panel.bench.lat.clone();
            xs.sort_by(|a, b| a.partial_cmp(b).unwrap());
            if !xs.is_empty() {
                println!("DISPATCH median {:.3} ms p95 {:.3} ms n={}", xs[xs.len() / 2], xs[xs.len() * 95 / 100], xs.len());
            }
            println!("FRAMES {} in {:.1} s = {:.1} per second", panel.bench.frames, panel.bench.start.elapsed().as_secs_f64(), panel.bench.frames as f64 / panel.bench.start.elapsed().as_secs_f64());
            panel.bench.secs = None;
            ctx.send_viewport_cmd(egui::ViewportCommand::Close);
        }
    }

    fn after_ui(&mut self) {
        self.frames += 1;
        if self.secs.is_some() && self.frames == 2 {
            let now = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_secs_f64();
            println!("READY {now:.4}");
        }
    }
}
// --- end bench
