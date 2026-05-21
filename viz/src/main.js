// Entry point: boot the shell and register the available visualizations.
// Each component registers itself by being imported (side effect).

import { mountShell } from "./shell.js";
import "./components/fileHeatmap.js";
import "./components/declHeatmap.js";

const root = document.getElementById("app");

mountShell(root).catch((err) => {
  const pre = document.createElement("pre");
  pre.className = "shell-error";
  pre.textContent = String((err && err.stack) || err);
  root.appendChild(pre);
});
