// GENERATED from viz/SPEC.md — section "Declaration edit heatmap".
// Do not hand-edit; edit the spec and regenerate.

import { el, svg, clear } from "../lib/dom.js";
import { register } from "./registry.js";
import { createRangeSlider } from "../lib/rangeSlider.js";
import { createClusterBar } from "../lib/clusterBar.js";
import {
  timeExtent,
  binFile,
  intensity,
  parseTime,
  formatTime,
  formatRange,
  humanDuration,
} from "../lib/scales.js";

const MIN_EDITS = 2; // show only decls touched in >= 2 edits

const M = { top: 10, right: 16, bottom: 30, left: 230 };
const ROW_H = 22;
const BAND_H = 9;
const BAND_GAP = 2;
const ROW_GAP = 3;
const FILE_HEADER_H = 26;
const FILE_GAP = 8;
const DEFAULT_BINS = 60;
const MIN_BINS = 8;
const MAX_BINS = 240;

function cssVar(root, name, fallback) {
  const v = getComputedStyle(root).getPropertyValue(name).trim();
  return v || fallback;
}

// Label a decl as "kind name"; for anonymous/empty names fall back to "kind @ Lline".
function declLabel(decl) {
  const kind = (decl.info && decl.info.kind) || "decl";
  const name = decl.info && decl.info.name;
  if (!name || name === "[anonymous]") {
    const line = (decl.range && decl.range.start && decl.range.start.line) || 0;
    return `${kind} @ L${line + 1}`;
  }
  return `${kind} ${name}`;
}

// data is exactly a DeclHeatmapInfo:
// { file_data: [ { file, decl_changes: [ { decl, change_events: [...] } ] } ] }
export function render(container, data, options = {}) {
  const fileData = (data && data.file_data) || [];

  const fileName = (f) => (typeof f.file === "string" ? f.file : String(f.file));
  const startLine = (d) =>
    (d.decl && d.decl.range && d.decl.range.start && d.decl.range.start.line) || 0;

  // Files in name order; within each file, decls in source (start-line) order, filtered
  // to >= MIN_EDITS. The Python side already sorts; the component enforces it too, so
  // the spec's stated order holds even if a given data file isn't sorted.
  const groups = [...fileData]
    .sort((a, b) => fileName(a).localeCompare(fileName(b)))
    .map((f) => ({
      file: fileName(f),
      decls: (f.decl_changes || [])
        .filter((d) => (d.change_events || []).length >= MIN_EDITS)
        .sort((a, b) => startLine(a) - startLine(b)),
    }))
    .filter((g) => g.decls.length > 0);

  // Shared time axis over every decl event in the data (stable regardless of filter).
  const allDecls = fileData.flatMap((f) => f.decl_changes || []);
  const [minMs, maxMs] = timeExtent(allDecls);

  // Time window the heatmap is drawn over (defaults to the full session span).
  let winStart = minMs;
  let winEnd = maxMs;

  const collapsed = new Set(); // file names that are collapsed; default all expanded

  const wrap = el("div", { class: "dh" });
  container.appendChild(wrap);
  wrap.appendChild(el("h3", { class: "dh-title", text: "Declaration edit heatmap" }));

  const slider = el("input", {
    type: "range",
    min: MIN_BINS,
    max: MAX_BINS,
    value: DEFAULT_BINS,
    class: "dh-slider",
  });
  const binLabel = el("span", { class: "dh-bin-label" });
  const windowSlider = createRangeSlider({
    min: minMs,
    max: maxMs,
    format: formatTime,
    onChange: (s, e) => setWindow(s, e, false),
  });
  const clusterBar = createClusterBar({
    min: minMs,
    max: maxMs,
    events: allDecls.flatMap((d) => d.change_events || []),
    defaultThresholdMin: 30,
    format: formatTime,
    onPick: (s, e) => setWindow(s, e),
  });
  const controls = el("div", { class: "dh-controls" }, [
    el("label", { class: "dh-control" }, [el("span", { text: "Time detail" }), slider, binLabel]),
    el("label", { class: "dh-control dh-control-window" }, [
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

  const caption = el("p", { class: "dh-caption" });
  wrap.appendChild(caption);

  const svgHost = el("div", { class: "dh-svg-host" });
  wrap.appendChild(svgHost);

  const tip = el("div", { class: "dh-tooltip", "aria-hidden": "true" });
  wrap.appendChild(tip);

  const addedColor = cssVar(wrap, "--dh-added", "#16a34a");
  const removedColor = cssVar(wrap, "--dh-removed", "#dc2626");
  const axisColor = cssVar(wrap, "--dh-axis", "#9ca3af");
  const textColor = cssVar(wrap, "--dh-text", "#374151");
  const headerColor = cssVar(wrap, "--dh-header", "#111827");

  function draw() {
    const nBins = Number(slider.value);
    const lo = winStart;
    const hi = Math.max(winEnd, winStart + 1); // guard against a zero-width window
    const winSpan = hi - lo;
    binLabel.textContent = `${nBins} bins · ~${humanDuration(winSpan / nBins)} each`;

    // Only show decls modified within the current window; drop file groups left empty.
    const visibleGroups = [];
    for (const g of groups) {
      const decls = g.decls.filter((d) =>
        d.change_events.some((e) => {
          const t = parseTime(e.time);
          return t >= lo && t <= hi;
        }),
      );
      if (decls.length) visibleGroups.push({ file: g.file, decls });
    }

    const shownDecls = visibleGroups.reduce((s, g) => s + g.decls.length, 0);
    caption.textContent =
      `${visibleGroups.length} file${visibleGroups.length === 1 ? "" : "s"} · ` +
      `${shownDecls} decl${shownDecls === 1 ? "" : "s"} shown · ` +
      `${formatTime(lo)} – ${formatTime(hi)}`;

    const plotW = Math.max(240, (svgHost.clientWidth || 960) - M.left - M.right);
    const cellW = plotW / nBins;

    // Bin every visible decl; track per-metric maxima across all visible bins.
    let maxAdded = 0;
    let maxRemoved = 0;
    for (const g of visibleGroups) {
      for (const d of g.decls) {
        d._bins = binFile(d.change_events, nBins, lo, hi);
        for (let i = 0; i < nBins; i++) {
          if (d._bins.added[i] > maxAdded) maxAdded = d._bins.added[i];
          if (d._bins.removed[i] > maxRemoved) maxRemoved = d._bins.removed[i];
        }
      }
    }

    // Total height depends on which files are expanded.
    let h = M.top;
    for (const g of visibleGroups) {
      h += FILE_HEADER_H;
      if (!collapsed.has(g.file)) h += g.decls.length * (ROW_H + ROW_GAP);
      h += FILE_GAP;
    }
    h += M.bottom;
    const w = M.left + plotW + M.right;

    const root = svg("svg", {
      class: "dh-svg",
      width: w,
      height: h,
      viewBox: `0 0 ${w} ${h}`,
      role: "img",
      "aria-label":
        "Declaration edit heatmap: characters added (green) and removed (red) per declaration over time",
    });

    let y = M.top;
    visibleGroups.forEach((g, gi) => {
      const isOpen = !collapsed.has(g.file);

      // --- clickable file header ---
      root.appendChild(
        svg("rect", {
          x: 0,
          y,
          width: w,
          height: FILE_HEADER_H - 4,
          rx: 4,
          class: "dh-file-header",
          "data-file": g.file,
        }),
      );
      root.appendChild(
        svg(
          "text",
          {
            x: 10,
            y: y + (FILE_HEADER_H - 4) / 2,
            "dominant-baseline": "middle",
            class: "dh-file-name",
            fill: headerColor,
            "pointer-events": "none",
          },
          `${isOpen ? "▾" : "▸"}  ${g.file}  (${g.decls.length})`,
        ),
      );
      y += FILE_HEADER_H;

      // --- decl rows (if expanded) ---
      if (isOpen) {
        g.decls.forEach((d, di) => {
          const label = declLabel(d.decl);
          root.appendChild(
            svg(
              "text",
              {
                x: M.left - 8,
                y: y + ROW_H / 2,
                "text-anchor": "end",
                "dominant-baseline": "middle",
                class: "dh-decl-label",
                fill: textColor,
              },
              [svg("title", {}, label), truncateRight(label, 34)],
            ),
          );
          for (let b = 0; b < nBins; b++) {
            const x = M.left + b * cellW;
            const a = d._bins.added[b];
            const rm = d._bins.removed[b];
            if (a > 0) {
              root.appendChild(
                cell(x, y, cellW, BAND_H, addedColor, intensity(a, maxAdded), gi, di, b),
              );
            }
            if (rm > 0) {
              root.appendChild(
                cell(
                  x,
                  y + BAND_H + BAND_GAP,
                  cellW,
                  BAND_H,
                  removedColor,
                  intensity(rm, maxRemoved),
                  gi,
                  di,
                  b,
                ),
              );
            }
          }
          y += ROW_H + ROW_GAP;
        });
      }
      y += FILE_GAP;
    });

    // --- shared time axis ---
    const yAxis = y - FILE_GAP + 4;
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
            class: "dh-axis-label",
            fill: textColor,
          },
          formatTime(lo + fr * winSpan),
        ),
      );
    }

    clear(svgHost).appendChild(root);

    // --- collapse/expand on file-header click; open diff page on cell click ---
    root.addEventListener("click", (ev) => {
      const header = ev.target.closest && ev.target.closest(".dh-file-header");
      if (header) {
        const file = header.getAttribute("data-file");
        if (collapsed.has(file)) collapsed.delete(file);
        else collapsed.add(file);
        draw();
        return;
      }
      const t = ev.target;
      if (!(t instanceof Element) || !t.classList.contains("dh-cell")) return;
      if (typeof options.onEditClick !== "function") return;
      const g = visibleGroups[Number(t.getAttribute("data-g"))];
      const d = g.decls[Number(t.getAttribute("data-d"))];
      const b = Number(t.getAttribute("data-b"));
      const span = hi - lo;
      const eventsInBin = d.change_events.filter((e) => {
        const ts = parseTime(e.time);
        if (ts < lo || ts > hi) return false;
        let idx = Math.floor(((ts - lo) / span) * nBins);
        if (idx >= nBins) idx = nBins - 1;
        if (idx < 0) idx = 0;
        return idx === b;
      });
      if (eventsInBin.length === 0) return;
      options.onEditClick(g.file, eventsInBin[0].edit_index);
    });

    // --- hover tooltip over cells ---
    root.addEventListener("mousemove", (ev) => {
      const t = ev.target;
      if (!(t instanceof Element) || !t.classList.contains("dh-cell")) {
        hideTip();
        return;
      }
      const g = visibleGroups[Number(t.getAttribute("data-g"))];
      const d = g.decls[Number(t.getAttribute("data-d"))];
      const b = Number(t.getAttribute("data-b"));
      const start = lo + (b / nBins) * winSpan;
      const end = lo + ((b + 1) / nBins) * winSpan;
      clear(tip);
      tip.appendChild(el("div", { class: "dh-tip-decl", text: declLabel(d.decl) }));
      tip.appendChild(el("div", { class: "dh-tip-file", text: g.file }));
      tip.appendChild(el("div", { class: "dh-tip-range", text: formatRange(start, end) }));
      tip.appendChild(
        el("div", { class: "dh-tip-counts" }, [
          el("span", { class: "dh-tip-add", text: `+${d._bins.added[b]}` }),
          el("span", { class: "dh-tip-rem", text: `−${d._bins.removed[b]}` }),
          el("span", { class: "dh-tip-unit", text: "chars" }),
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

  function cell(x, y, w, h, fill, opacity, gi, di, b) {
    return svg("rect", {
      x,
      y,
      width: Math.max(0.5, w - 0.5),
      height: h,
      fill,
      "fill-opacity": opacity.toFixed(3),
      class: "dh-cell",
      "data-g": gi,
      "data-d": di,
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
  return el("div", { class: "dh-legend" }, [
    legendItem(cssVar(root, "--dh-added", "#16a34a"), "added"),
    legendItem(cssVar(root, "--dh-removed", "#dc2626"), "removed"),
  ]);
}

function legendItem(color, label) {
  return el("span", { class: "dh-legend-item" }, [
    el("span", { class: "dh-legend-swatch", style: `background:${color}` }),
    el("span", { text: label }),
  ]);
}

// Keep the start of a decl label (kind + name beginning); ellipsize the tail.
function truncateRight(s, n) {
  return s.length <= n ? s : s.slice(0, n - 1) + "…";
}

register("decl_heatmap", render);
