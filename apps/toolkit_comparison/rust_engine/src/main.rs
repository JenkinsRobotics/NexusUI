//! The bench supply panel's engine written in Rust, serving the same React UI as app.py.
//!
//! This is the "Rust backend, React/TypeScript screen" combination. It speaks the part of
//! the NexusUI protocol this one panel needs (values, writes, one command, stations);
//! it has no alerts, event log, history, layouts editor or control lock.
//!
//! Run:  cargo run --release -- --desktop      (from apps/toolkit_comparison/rust_engine)
use axum::extract::ws::{Message, WebSocket, WebSocketUpgrade};
use axum::extract::{Query, State};
use axum::http::header::CONTENT_TYPE;
use axum::response::IntoResponse;
use axum::routing::get;
use axum::{Json, Router};
use futures_util::{SinkExt, StreamExt};
use serde_json::{Map, Value, json};
use std::collections::HashMap;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tokio::sync::mpsc::{UnboundedSender, unbounded_channel};
use tower_http::services::ServeDir;

const CATALOG: &str = include_str!("../assets/catalog.json"); // channel and command descriptions, as app.py reports them
const WIDGETS: &str = include_str!("../assets/widgets.json");
const LAYOUT: &str = include_str!("../../layouts/default.json");
const UI_DIR: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/../../../framework/nexusui/ui_dist");
const LOAD_OHMS: f64 = 8.0;
const TRIP_C: f64 = 85.0;
const RESET_C: f64 = 50.0;
const FRAME_RATE: f64 = 30.0; // same as NexusUI's default

fn now() -> f64 {
    SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs_f64()
}

struct Station {
    id: String,
    name: String,
    since: f64,
    tx: UnboundedSender<String>,
}

struct Engine {
    output: bool,
    vset: f64,
    fan: String,
    v: f64,
    i: f64,
    t: f64,
    tripped: bool,
    noise: u64,
    sent: Map<String, Value>,
    stations: Vec<Station>,
    next_id: u64,
    started: f64,
}

type Shared = Arc<Mutex<Engine>>;

impl Engine {
    fn new() -> Self {
        Self {
            output: false,
            vset: 12.0,
            fan: "AUTO".into(),
            v: 0.0,
            i: 0.0,
            t: 25.0,
            tripped: false,
            noise: 0x9E3779B97F4A7C15,
            sent: Map::new(),
            stations: Vec::new(),
            next_id: 1,
            started: now(),
        }
    }

    fn step(&mut self, dt: f64) {
        self.noise ^= self.noise << 13;
        self.noise ^= self.noise >> 7;
        self.noise ^= self.noise << 17;
        let jitter = ((self.noise % 2001) as f64 / 1000.0 - 1.0) * 0.007;
        let target = if self.output { self.vset } else { 0.0 };
        self.v += (target - self.v) * (dt / 0.15).min(1.0);
        self.i = if self.v > 0.01 { self.v / LOAD_OHMS * (1.0 + jitter) } else { 0.0 };
        let airflow = match self.fan.as_str() {
            "LOW" => 0.3,
            "HIGH" => 1.0,
            _ => ((self.t - 40.0) / 20.0).clamp(0.2, 1.0),
        };
        self.t += (self.v * self.i * 0.9 - (self.t - 25.0) * (0.4 + 1.6 * airflow)) * dt / 6.0;
        if self.t >= TRIP_C && !self.tripped {
            self.tripped = true;
            self.output = false;
        }
    }

    fn values(&self) -> Map<String, Value> {
        let state = if self.tripped { "FAULT" } else if self.output { "RUNNING" } else { "IDLE" };
        let v = json!({
            "psu.output": self.output, "psu.vset": self.vset, "psu.voltage": self.v, "psu.current": self.i,
            "board.temp": self.t, "board.fan": self.fan, "board.state": state, "board.tripped": self.tripped,
        });
        v.as_object().unwrap().clone()
    }

    fn broadcast(&self, msg: &Value) {
        let text = msg.to_string();
        for s in &self.stations {
            let _ = s.tx.send(text.clone());
        }
    }

    /// Send every value that changed since the last frame. A write also names who made it.
    fn flush(&mut self, write: Option<(&str, &str)>) {
        let mut changed = Map::new();
        for (name, value) in self.values() {
            if self.sent.get(&name) != Some(&value) || write.is_some_and(|(ch, _)| ch == name) {
                self.sent.insert(name.clone(), value.clone());
                changed.insert(name, value);
            }
        }
        if changed.is_empty() {
            return;
        }
        let mut msg = json!({"t": "d", "ts": now(), "v": changed});
        if let Some((ch, by)) = write {
            msg["w"] = json!({ ch: {"by": by, "ts": now()} });
        }
        self.broadcast(&msg);
    }

    fn station_list(&self) -> Value {
        self.stations.iter().map(|s| json!({"id": s.id, "name": s.name, "addr": "127.0.0.1", "since": s.since})).collect()
    }

    fn write(&mut self, ch: &str, v: &Value) -> Result<(), String> {
        match (ch, v) {
            ("psu.output", Value::Bool(on)) => {
                if *on && self.tripped {
                    return Err("Output locked: over-temperature trip; let the board cool, then press Reset Trip".into());
                }
                self.output = *on;
            }
            ("psu.vset", Value::Number(n)) => {
                let x = n.as_f64().unwrap_or(f64::NAN);
                if !(0.0..=24.0).contains(&x) {
                    return Err("Setpoint must be between 0 and 24 V".into());
                }
                self.vset = x;
            }
            ("board.fan", Value::String(s)) if ["AUTO", "LOW", "HIGH"].contains(&s.as_str()) => self.fan = s.clone(),
            _ => return Err(format!("Cannot write {v} to {ch}")),
        }
        Ok(())
    }
}

fn handle(eng: &Shared, id: &str, m: &Value) {
    let mut e = eng.lock().unwrap();
    let Some(st) = e.stations.iter().find(|s| s.id == id) else { return };
    let (tx, name) = (st.tx.clone(), st.name.clone());
    let ack = |result: Result<(), String>| {
        let msg = match result {
            Ok(()) => json!({"t": "ack", "id": m["id"], "ok": true}),
            Err(why) => json!({"t": "ack", "id": m["id"], "ok": false, "error": why}),
        };
        let _ = tx.send(msg.to_string());
    };
    match m["t"].as_str() {
        Some("ping") => {
            let _ = tx.send(json!({"t": "pong", "id": m["id"], "ct": m["ct"], "st": now()}).to_string());
        }
        Some("write") => {
            let ch = m["ch"].as_str().unwrap_or("");
            let result = e.write(ch, &m["v"]);
            if result.is_ok() {
                e.flush(Some((ch, &name))); // every station sees the change before the writer gets its ack
            }
            ack(result);
        }
        Some("cmd") => ack(match m["name"].as_str() {
            Some("psu.reset_trip") if e.t > RESET_C => Err(format!("Board is still above {RESET_C} °C")),
            Some("psu.reset_trip") => {
                e.tripped = false;
                Ok(())
            }
            other => Err(format!("Unknown command {other:?}")),
        }),
        Some("claim" | "release" | "override") => ack(Ok(())),
        _ => {}
    }
}

async fn station(socket: WebSocket, name: String, eng: Shared) {
    let (mut sink, mut stream) = socket.split();
    let (tx, mut rx) = unbounded_channel::<String>();
    let (id, hello) = {
        let mut e = eng.lock().unwrap();
        let id = format!("s{}", e.next_id);
        e.next_id += 1;
        let name = if name.is_empty() { format!("Station {}", &id[1..]) } else { name };
        let you = json!({"id": id, "name": name, "addr": "127.0.0.1", "since": now()});
        e.stations.push(Station { id: id.clone(), name, since: now(), tx: tx.clone() });
        let catalog: Value = serde_json::from_str(CATALOG).unwrap();
        let hello = json!({
            "t": "hello", "ts": now(), "you": you,
            "engine": {"name": "Bench Supply", "control": "open", "frame_rate": FRAME_RATE, "watchdog": 1.5, "started_at": e.started},
            "channels": catalog["channels"], "commands": catalog["commands"], "devices": [], "diagrams": [],
            "values": e.values(), "writes": {},
            "control": {"t": "control", "mode": "open", "holder": null, "holder_name": null, "override": false, "override_by": null},
            "stations": e.station_list(), "alerts": [], "logs": [], "locks": {},
            "history": {"t": [], "v": {"psu.vset": [], "psu.voltage": [], "psu.current": [], "board.temp": []}},
        });
        e.broadcast(&json!({"t": "stations", "list": e.station_list()}));
        (id, hello.to_string())
    };
    if sink.send(Message::Text(hello.into())).await.is_err() {
        return;
    }
    let sender = tokio::spawn(async move {
        while let Some(text) = rx.recv().await {
            if sink.send(Message::Text(text.into())).await.is_err() {
                break;
            }
        }
    });
    while let Some(Ok(msg)) = stream.next().await {
        if let Message::Text(text) = msg {
            if let Ok(m) = serde_json::from_str::<Value>(text.as_str()) {
                handle(&eng, &id, &m);
            }
        }
    }
    sender.abort();
    let mut e = eng.lock().unwrap();
    e.stations.retain(|s| s.id != id);
    e.broadcast(&json!({"t": "stations", "list": e.station_list()}));
}

async fn serve(eng: Shared, listener: std::net::TcpListener) {
    let json_text = |text: &'static str| move || async move { ([(CONTENT_TYPE, "application/json")], text) };
    let app = Router::new()
        .route("/ws", get(|ws: WebSocketUpgrade, Query(q): Query<HashMap<String, String>>, State(eng): State<Shared>| async move {
            let name = q.get("name").cloned().unwrap_or_default();
            ws.on_upgrade(move |socket| station(socket, name, eng)).into_response()
        }))
        .route("/api/info", get(|State(eng): State<Shared>| async move {
            let e = eng.lock().unwrap();
            Json(json!({"name": "Bench Supply", "control": "open", "stations": e.stations.len(), "uptime": now() - e.started}))
        }))
        .route("/api/widgets", get(json_text(WIDGETS)))
        .route("/api/layouts", get(|| async { Json(json!({"layouts": [{"name": "default", "title": "Bench Supply", "mtime": 0}], "default": "default"})) }))
        .route("/api/layouts/default", get(json_text(LAYOUT)))
        .fallback_service(ServeDir::new(UI_DIR))
        .with_state(eng.clone());

    let flusher = tokio::spawn(async move {
        let mut tick = tokio::time::interval(Duration::from_secs_f64(1.0 / FRAME_RATE));
        loop {
            tick.tick().await;
            eng.lock().unwrap().flush(None);
        }
    });
    listener.set_nonblocking(true).unwrap();
    axum::serve(tokio::net::TcpListener::from_std(listener).unwrap(), app).await.unwrap();
    flusher.abort();
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let port: u16 = args.iter().position(|a| a == "--port").and_then(|n| args.get(n + 1)).and_then(|p| p.parse().ok()).unwrap_or(8000);
    let listener = std::net::TcpListener::bind(("0.0.0.0", port)).unwrap_or_else(|e| {
        eprintln!("could not start on port {port}: {e}");
        std::process::exit(1);
    });
    let eng: Shared = Arc::new(Mutex::new(Engine::new()));

    let hardware = eng.clone();
    std::thread::spawn(move || {
        let mut next = Instant::now();
        loop {
            hardware.lock().unwrap().step(0.02);
            next += Duration::from_millis(20);
            std::thread::sleep(next.saturating_duration_since(Instant::now()));
        }
    });

    let runtime = tokio::runtime::Builder::new_multi_thread().worker_threads(2).enable_all().build().unwrap();
    println!("[Bench Supply] UI at http://localhost:{port}");
    if !args.iter().any(|a| a == "--desktop") {
        runtime.block_on(serve(eng, listener));
        return;
    }
    runtime.spawn(serve(eng, listener));

    use tao::event::{Event, WindowEvent};
    use tao::event_loop::{ControlFlow, EventLoop};
    let event_loop = EventLoop::new();
    let window = tao::window::WindowBuilder::new()
        .with_title("Bench Supply")
        .with_inner_size(tao::dpi::LogicalSize::new(1600.0, 950.0))
        .build(&event_loop)
        .unwrap();
    let _webview = wry::WebViewBuilder::new().with_url(format!("http://127.0.0.1:{port}/")).build(&window).unwrap();
    event_loop.run(move |event, _, control_flow| {
        *control_flow = ControlFlow::Wait;
        if let Event::WindowEvent { event: WindowEvent::CloseRequested, .. } = event {
            *control_flow = ControlFlow::Exit;
        }
    });
}
