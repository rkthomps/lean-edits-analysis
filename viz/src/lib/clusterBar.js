// A row of "session" buttons derived from gap-based clustering, plus a gap-threshold
// selector and an "All" button. Clicking a session calls onPick(startMs, endMs) so a
// host can zoom its time window to that cluster. Shared by the heatmaps.
//
// Returns { element, setActiveRange(startMs, endMs) }.

import { el, clear } from "./dom.js";
import { clusterByGap, humanDuration } from "./scales.js";

const PRESETS_MIN = [5, 10, 15, 30, 60, 120]; // gap thresholds, minutes

export function createClusterBar({
  min,
  max,
  events,
  defaultThresholdMin = 30,
  format,
  onPick,
} = {}) {
  const fmt = format || ((v) => String(v));
  let thresholdMin = defaultThresholdMin;

  const select = el("select", { class: "cb-threshold", "aria-label": "Session gap" });
  for (const m of PRESETS_MIN) {
    const opt = el("option", { value: m, text: m < 60 ? `${m} min` : `${m / 60} h` });
    if (m === thresholdMin) opt.selected = true;
    select.appendChild(opt);
  }

  const allBtn = el("button", { type: "button", class: "cb-chip cb-all", text: "All" });
  const chips = el("div", { class: "cb-chips" });

  const element = el("div", { class: "cb" }, [
    el("span", { class: "cb-label", text: "Sessions" }),
    el("label", { class: "cb-gap" }, [el("span", { text: "gap" }), select]),
    allBtn,
    chips,
  ]);

  let buttons = []; // { el, startMs, endMs }

  function rebuild() {
    clear(chips);
    buttons = [];
    const clusters = clusterByGap(events, thresholdMin * 60 * 1000);
    clusters.forEach((c) => {
      const btn = el(
        "button",
        {
          type: "button",
          class: "cb-chip",
          title: `${fmt(c.startMs)} – ${fmt(c.endMs)} · ${c.count} edits · ${humanDuration(c.endMs - c.startMs)}`,
          onClick: () => onPick && onPick(c.startMs, c.endMs),
        },
        `${fmt(c.startMs)} · ${c.count}`,
      );
      chips.appendChild(btn);
      buttons.push({ el: btn, startMs: c.startMs, endMs: c.endMs });
    });
  }

  function setActiveRange(s, e) {
    const isAll = s <= min && e >= max;
    allBtn.classList.toggle("is-active", isAll);
    for (const b of buttons) {
      const match = !isAll && Math.abs(b.startMs - s) < 1 && Math.abs(b.endMs - e) < 1;
      b.el.classList.toggle("is-active", match);
    }
  }

  select.addEventListener("change", () => {
    thresholdMin = Number(select.value);
    rebuild();
  });
  allBtn.addEventListener("click", () => onPick && onPick(min, max));

  rebuild();

  return { element, setActiveRange };
}
