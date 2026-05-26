// GENERATED from viz/SPEC.md — section "File edit heatmap".
// Do not hand-edit; edit the spec and regenerate.

import { el, svg, clear } from "../lib/dom.js";
import { register } from "./registry.js";
import { createRangeSlider } from "../lib/rangeSlider.js";
import { createClusterBar } from "../lib/clusterBar.js";
import {
  timeExtent,
  binAll,
  intensity,
  orderByFirstEdit,
  parseTime,
  formatTime,
  formatRange,
  humanDuration,
} from "../lib/scales.js";

const M = { top: 10, right: 16, bottom: 30, left: 180 };
const ROW_H = 26;
const BAND_H = 11;
const BAND_GAP = 2;
const ROW_GAP = 4;
const DEFAULT_BINS = 60;
const MIN_BINS = 8;
const MAX_BINS = 240;

// Read a CSS custom property off the component root, with a fallback.
function cssVar(root, name, fallback) {
  const v = getComputedStyle(root).getPropertyValue(name).trim();
  return v || fallback;
}

// data is exactly a FileHeatmapInfo: { file_data: [ { file, change_events: [...] } ] }
export function render(container, data, options = {}) {
  const fileData = orderByFirstEdit((data && data.file_data) || []);
  const [minMs, maxMs] = timeExtent(fileData);

  // Time window the heatmap is drawn over (defaults to the full session span).
  let winStart = minMs;
  let winEnd = maxMs;

  const wrap = el("div", { class: "fh" });
  container.appendChild(wrap);
  wrap.appendChild(el("h3", { class: "fh-title", text: "File edit heatmap" }));

  // --- controls: bin-size slider + time-window slider + legend ---
  const slider = el("input", {
    type: "range",
    min: MIN_BINS,
    max: MAX_BINS,
    value: DEFAULT_BINS,
    class: "fh-slider",
  });
  const binLabel = el("span", { class: "fh-bin-label" });
  const windowSlider = createRangeSlider({
    min: minMs,
    max: maxMs,
    format: formatTime,
    onChange: (s, e) => setWindow(s, e, false),
  });
  const clusterBar = createClusterBar({
    min: minMs,
    max: maxMs,
    events: fileData.flatMap((f) => f.change_events || []),
    defaultThresholdMin: 30,
    format: formatTime,
    onPick: (s, e) => setWindow(s, e),
  });
  const controls = el("div", { class: "fh-controls" }, [
    el("label", { class: "fh-control" }, [el("span", { text: "Time detail" }), slider, binLabel]),
    el("label", { class: "fh-control fh-control-window" }, [
      el("span", { text: "Time window" }),
      windowSlider.element,
    ]),
    legend(wrap),
  ]);
  wrap.appendChild(controls);
  wrap.appendChild(clusterBar.element);

  // Set the visible window (from a cluster pick or the slider) and redraw.
  function setWindow(s, e, syncSlider = true) {
    winStart = s;
    winEnd = e;
    if (syncSlider) windowSlider.setRange(s, e);
    clusterBar.setActiveRange(s, e);
    draw();
  }

  wrap.appendChild(
    el("p", {
      class: "fh-caption",
      text:
        `${fileData.length} file${fileData.length === 1 ? "" : "s"} · ` +
        `${formatTime(minMs)} – ${formatTime(maxMs)}`,
    }),
  );

  const svgHost = el("div", { class: "fh-svg-host" });
  wrap.appendChild(svgHost);

  const tip = el("div", { class: "fh-tooltip", "aria-hidden": "true" });
  wrap.appendChild(tip);

  // --- cell click → open diff page ---
  svgHost.addEventListener("click", (ev) => {
    const target = ev.target;
    if (!(target instanceof Element) || !target.classList.contains("fh-cell")) return;
    if (typeof options.onEditClick !== "function") return;
    const fi = Number(target.getAttribute("data-f"));
    const b = Number(target.getAttribute("data-b"));
    const nBins = Number(slider.value);
    const lo = winStart;
    const hi = Math.max(winEnd, winStart + 1);
    const span = hi - lo;
    const eventsInBin = fileData[fi].change_events.filter((e) => {
      const t = parseTime(e.time);
      if (t < lo || t > hi) return false;
      let idx = Math.floor(((t - lo) / span) * nBins);
      if (idx >= nBins) idx = nBins - 1;
      if (idx < 0) idx = 0;
      return idx === b;
    });
    if (eventsInBin.length === 0) return;
    options.onEditClick(String(fileData[fi].file), eventsInBin[0].edit_index);
  });

  const addedColor = cssVar(wrap, "--fh-added", "#16a34a");
  const removedColor = cssVar(wrap, "--fh-removed", "#dc2626");
  const axisColor = cssVar(wrap, "--fh-axis", "#9ca3af");
  const textColor = cssVar(wrap, "--fh-text", "#374151");

  function draw() {
    const nBins = Number(slider.value);
    const lo = winStart;
    const hi = Math.max(winEnd, winStart + 1); // guard against a zero-width window
    const winSpan = hi - lo;
    binLabel.textContent = `${nBins} bins · ~${humanDuration(winSpan / nBins)} each`;

    const plotW = Math.max(240, (svgHost.clientWidth || 960) - M.left - M.right);
    const cellW = plotW / nBins;
    const h = M.top + fileData.length * (ROW_H + ROW_GAP) + M.bottom;
    const w = M.left + plotW + M.right;

    const { rows, maxAdded, maxRemoved } = binAll(fileData, nBins, lo, hi);

    const root = svg("svg", {
      class: "fh-svg",
      width: w,
      height: h,
      viewBox: `0 0 ${w} ${h}`,
      role: "img",
      "aria-label": "File edit heatmap: characters added (green) and removed (red) over time",
    });

    rows.forEach((r, fi) => {
      const yTop = M.top + fi * (ROW_H + ROW_GAP);
      root.appendChild(
        svg(
          "text",
          {
            x: M.left - 8,
            y: yTop + ROW_H / 2,
            "text-anchor": "end",
            "dominant-baseline": "middle",
            class: "fh-file-label",
            fill: textColor,
          },
          truncateLeft(r.file, 26),
        ),
      );
      for (let b = 0; b < nBins; b++) {
        const x = M.left + b * cellW;
        if (r.added[b] > 0) {
          root.appendChild(
            cell(x, yTop, cellW, BAND_H, addedColor, intensity(r.added[b], maxAdded), fi, b),
          );
        }
        if (r.removed[b] > 0) {
          root.appendChild(
            cell(
              x,
              yTop + BAND_H + BAND_GAP,
              cellW,
              BAND_H,
              removedColor,
              intensity(r.removed[b], maxRemoved),
              fi,
              b,
            ),
          );
        }
      }
    });

    // --- time axis ---
    const yAxis = M.top + fileData.length * (ROW_H + ROW_GAP) + 4;
    const ticks = 6;
    for (let i = 0; i <= ticks; i++) {
      const fr = i / ticks;
      const x = M.left + fr * plotW;
      root.appendChild(
        svg("line", { x1: x, y1: yAxis, x2: x, y2: yAxis + 4, stroke: axisColor }),
      );
      root.appendChild(
        svg(
          "text",
          {
            x,
            y: yAxis + 16,
            "text-anchor": i === 0 ? "start" : i === ticks ? "end" : "middle",
            class: "fh-axis-label",
            fill: textColor,
          },
          formatTime(lo + fr * winSpan),
        ),
      );
    }

    clear(svgHost).appendChild(root);

    // --- hover tooltip (event delegation over the cells) ---
    root.addEventListener("mousemove", (ev) => {
      const target = ev.target;
      if (!(target instanceof Element) || !target.classList.contains("fh-cell")) {
        hideTip();
        return;
      }
      const fi = Number(target.getAttribute("data-f"));
      const b = Number(target.getAttribute("data-b"));
      const r = rows[fi];
      const start = lo + (b / nBins) * winSpan;
      const end = lo + ((b + 1) / nBins) * winSpan;
      clear(tip);
      tip.appendChild(el("div", { class: "fh-tip-file", text: r.file }));
      tip.appendChild(el("div", { class: "fh-tip-range", text: formatRange(start, end) }));
      tip.appendChild(
        el("div", { class: "fh-tip-counts" }, [
          el("span", { class: "fh-tip-add", text: `+${r.added[b]}` }),
          el("span", { class: "fh-tip-rem", text: `−${r.removed[b]}` }),
          el("span", { class: "fh-tip-unit", text: "chars" }),
        ]),
      );
      const box = wrap.getBoundingClientRect();
      tip.style.left = `${ev.clientX - box.left + 12}px`;
      tip.style.top = `${ev.clientY - box.top + 12}px`;
      tip.classList.add("is-visible");
      tip.setAttribute("aria-hidden", "false");
    });
    root.addEventListener("mouseleave", hideTip);

    function hideTip() {
      tip.classList.remove("is-visible");
      tip.setAttribute("aria-hidden", "true");
    }
  }

  function cell(x, y, w, h, fill, opacity, fi, b) {
    return svg("rect", {
      x,
      y,
      width: Math.max(0.5, w - 0.5),
      height: h,
      fill,
      "fill-opacity": opacity.toFixed(3),
      class: "fh-cell",
      "data-f": fi,
      "data-b": b,
    });
  }

  slider.addEventListener("input", draw);

  let resizeRaf = 0;
  window.addEventListener("resize", () => {
    cancelAnimationFrame(resizeRaf);
    resizeRaf = requestAnimationFrame(draw);
  });

  clusterBar.setActiveRange(winStart, winEnd);
  draw();
}

function legend(root) {
  return el("div", { class: "fh-legend" }, [
    legendItem(cssVar(root, "--fh-added", "#16a34a"), "added"),
    legendItem(cssVar(root, "--fh-removed", "#dc2626"), "removed"),
  ]);
}

function legendItem(color, label) {
  return el("span", { class: "fh-legend-item" }, [
    el("span", { class: "fh-legend-swatch", style: `background:${color}` }),
    el("span", { text: label }),
  ]);
}

// Keep the tail (filename) when a path is too long for the label gutter.
function truncateLeft(s, n) {
  return s.length <= n ? s : "…" + s.slice(s.length - n + 1);
}

register("file_heatmap", render);
