// A dual-handle range slider over [min, max], built from two overlaid native range
// inputs (no dependencies). Calls onChange(start, end) live as either handle moves.
// Shared by visualizations that need a draggable time window.
//
// Returns { element, getRange(), setRange(start, end), reset() }.

import { el } from "./dom.js";

export function createRangeSlider({ min, max, step, format, onChange } = {}) {
  step = step || Math.max(1, Math.floor((max - min) / 1000));
  const fmt = format || ((v) => String(v));

  const startInput = el("input", {
    type: "range", min, max, step, value: min, class: "rs-input rs-start",
    "aria-label": "Window start",
  });
  const endInput = el("input", {
    type: "range", min, max, step, value: max, class: "rs-input rs-end",
    "aria-label": "Window end",
  });

  const fill = el("div", { class: "rs-fill" });
  const track = el("div", { class: "rs-track" }, [fill]);
  const row = el("div", { class: "rs-row" }, [track, startInput, endInput]);

  const startLabel = el("span", { class: "rs-label" });
  const endLabel = el("span", { class: "rs-label" });
  const reset = el("button", { type: "button", class: "rs-reset", text: "Reset" });
  const labels = el("div", { class: "rs-labels" }, [startLabel, reset, endLabel]);

  const element = el("div", { class: "rs" }, [row, labels]);

  function clampOrder(which) {
    let s = Number(startInput.value);
    let e = Number(endInput.value);
    if (s > e) {
      if (which === "start") s = e;
      else e = s;
      startInput.value = s;
      endInput.value = e;
    }
    return [s, e];
  }

  function paint(s, e) {
    const pct = (v) => ((v - min) / (max - min || 1)) * 100;
    fill.style.left = `${pct(s)}%`;
    fill.style.right = `${100 - pct(e)}%`;
    startLabel.textContent = fmt(s);
    endLabel.textContent = fmt(e);
    // Keep the handle nearer the middle on top so an overlapped handle stays grabbable.
    const mid = (min + max) / 2;
    startInput.style.zIndex = s > mid ? "4" : "3";
    endInput.style.zIndex = e < mid ? "4" : "3";
  }

  function emit(which) {
    const [s, e] = clampOrder(which);
    paint(s, e);
    if (onChange) onChange(s, e);
  }

  startInput.addEventListener("input", () => emit("start"));
  endInput.addEventListener("input", () => emit("end"));
  reset.addEventListener("click", () => {
    startInput.value = min;
    endInput.value = max;
    emit("end");
  });

  paint(min, max);

  return {
    element,
    getRange: () => [Number(startInput.value), Number(endInput.value)],
    setRange: (s, e) => {
      startInput.value = s;
      endInput.value = e;
      paint(s, e);
    },
    reset: () => {
      startInput.value = min;
      endInput.value = max;
      paint(min, max);
    },
  };
}
