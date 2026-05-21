// Pure helpers for the file heatmap: time binning + color intensity.
// No DOM here, so this module is unit-testable on its own.

// Parse an ISO timestamp (the data has no timezone suffix) to epoch ms.
export function parseTime(iso) {
  return new Date(iso).getTime();
}

// [minMs, maxMs] across every change_event in a FileHeatmapInfo's file_data.
export function timeExtent(fileData) {
  let min = Infinity;
  let max = -Infinity;
  for (const f of fileData) {
    for (const e of f.change_events) {
      const t = parseTime(e.time);
      if (t < min) min = t;
      if (t > max) max = t;
    }
  }
  if (!isFinite(min)) return [0, 1];
  if (min === max) return [min, min + 1];
  return [min, max];
}

// Bin one file's events into nBins columns over the window [minMs, maxMs].
// Events outside the window are dropped (so a narrowed window excludes them rather
// than piling them onto the edge bins). Returns { added: number[nBins], removed: number[nBins] }.
export function binFile(changeEvents, nBins, minMs, maxMs) {
  const added = new Array(nBins).fill(0);
  const removed = new Array(nBins).fill(0);
  const span = maxMs - minMs;
  for (const e of changeEvents) {
    const t = parseTime(e.time);
    if (t < minMs || t > maxMs) continue; // outside the window
    let idx = Math.floor(((t - minMs) / span) * nBins);
    if (idx >= nBins) idx = nBins - 1; // fold the right edge into the last bin
    if (idx < 0) idx = 0;
    added[idx] += e.characters_added || 0;
    removed[idx] += e.characters_removed || 0;
  }
  return { added, removed };
}

// Bin every file, and report the per-metric maxima used for color scaling.
// added and removed are scaled independently (see SPEC.md "Color").
export function binAll(fileData, nBins, minMs, maxMs) {
  const rows = fileData.map((f) => ({
    file: typeof f.file === "string" ? f.file : String(f.file),
    ...binFile(f.change_events, nBins, minMs, maxMs),
  }));
  let maxAdded = 0;
  let maxRemoved = 0;
  for (const r of rows) {
    for (let i = 0; i < nBins; i++) {
      if (r.added[i] > maxAdded) maxAdded = r.added[i];
      if (r.removed[i] > maxRemoved) maxRemoved = r.removed[i];
    }
  }
  return { rows, maxAdded, maxRemoved };
}

// Map a value in [0, max] to a fill opacity. 0 -> 0 (blank cell).
// sqrt eases the heavy-tailed distribution so small bins stay visible.
export function intensity(value, max) {
  if (value <= 0 || max <= 0) return 0;
  const t = Math.sqrt(value / max);
  return 0.15 + 0.85 * Math.min(1, t);
}

// Split events into clusters ("working sessions") wherever the gap between consecutive
// events exceeds thresholdMs. Returns [{ startMs, endMs, count }] in time order.
export function clusterByGap(events, thresholdMs) {
  const times = events
    .map((e) => parseTime(e.time))
    .filter((t) => !Number.isNaN(t))
    .sort((a, b) => a - b);
  if (times.length === 0) return [];

  const clusters = [];
  let start = times[0];
  let last = times[0];
  let count = 1;
  for (let i = 1; i < times.length; i++) {
    const t = times[i];
    if (t - last > thresholdMs) {
      clusters.push({ startMs: start, endMs: last, count });
      start = t;
      count = 1;
    } else {
      count++;
    }
    last = t;
  }
  clusters.push({ startMs: start, endMs: last, count });
  return clusters;
}

// Order files by the time of their first event (earliest first).
export function orderByFirstEdit(fileData) {
  return [...fileData].sort(
    (a, b) => firstTime(a.change_events) - firstTime(b.change_events),
  );
}

function firstTime(events) {
  let min = Infinity;
  for (const e of events) {
    const t = parseTime(e.time);
    if (t < min) min = t;
  }
  return min;
}

// Short axis/tooltip label for an epoch-ms timestamp.
export function formatTime(ms) {
  const d = new Date(ms);
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

// "start – end" label for a bin's time range.
export function formatRange(startMs, endMs) {
  return `${formatTime(startMs)} – ${formatTime(endMs)}`;
}

// Human-friendly duration for the bin-width readout.
export function humanDuration(ms) {
  const s = ms / 1000;
  if (s < 90) return `${Math.round(s)}s`;
  const m = s / 60;
  if (m < 90) return `${Math.round(m)}m`;
  const h = m / 60;
  if (h < 48) return `${h.toFixed(1)}h`;
  return `${(h / 24).toFixed(1)}d`;
}
