import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/600.css";
import "./styles.css";
import App from "./App";
import { StationCtx } from "./lib/hooks";
import { Station } from "./lib/store";

const proto = location.protocol === "https:" ? "wss" : "ws";
const station = new Station(`${proto}://${location.host}/ws`);
station.start();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <StationCtx.Provider value={station}>
      <App />
    </StationCtx.Provider>
  </StrictMode>,
);
