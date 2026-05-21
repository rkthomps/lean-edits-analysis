# Visualization conventions (for agents)

> **`SPEC.md` is the source of truth for *what* the visualizations are. This file
> defines *how* they are built.** The JavaScript in `viz/` is generated from
> `SPEC.md`. Never hand-edit generated code to change behavior — change `SPEC.md`,
> then regenerate. This file is the fixed frame that keeps every regeneration
> consistent.

## Audience

Kyle edits `SPEC.md` only. He is not a front-end developer and does not read this
file day to day. Keep `SPEC.md` plain and jargon-free; keep all mechanics here.

## Architecture

Three layers separated by a JSON boundary. Do not change this shape without Kyle's
sign-off.

1. **Data (Python)** — pure functions turn analysis output into JSON. No rendering,
   no HTML.
2. **Component (vanilla JS)** — one module per visualization draws interactive
   inline SVG from that JSON.
3. **Shell (vanilla JS)** — a single-page host with a session switcher that composes
   one or more views onto a page.

## Hard constraints

- Vanilla ES modules. **No framework** (React/Vue/Svelte), **no build step**, no
  bundler.
- **No external/CDN dependencies.** Everything runs offline. (This is what keeps the
  app droppable into a VSCode webview later.)
- Charts are **hand-built inline SVG**. No charting library.
- A component draws **only inside the container element it is handed**.
- Every CSS class a component uses is **prefixed** with a short component tag (e.g.
  `fh-` for `fileHeatmap`). No global or unprefixed selectors.
- Prefer reading CSS variables for colors (with sane fallbacks) so a VSCode theme can
  override them later.

## Directory layout

Rooted at `viz/`:

```
viz/
  SPEC.md                    # source of truth (Kyle edits this)
  CONVENTIONS.md             # this file (agents follow this)
  index.html                 # the single-page shell
  src/
    main.js                  # boot: load manifest, build sidebar, show a session
    shell.js                 # layout + session/view switching
    data.js                  # fetch manifest.json and session JSON
    components/
      registry.js            # maps a view "kind" -> its render function
      fileHeatmap.js         # export render(el, data, opts) — file_heatmap
      declHeatmap.js         # export render(el, data, opts) — decl_heatmap
    lib/
      dom.js                 # tiny element/SVG builder helper
      scales.js              # time-bin, color-scale, and gap-clustering helpers
      rangeSlider.js         # shared dual-handle range slider (createRangeSlider)
      clusterBar.js          # shared session-cluster button bar (createClusterBar)
    styles/
      shell.css              # shell layout
      rangeSlider.css        # range slider styles, classes prefixed "rs-"
      clusterBar.css         # cluster bar styles, classes prefixed "cb-"
      fileHeatmap.css        # component styles, classes prefixed "fh-"
      declHeatmap.css        # component styles, classes prefixed "dh-"
  data/                      # JSON written by the Python side (generated)
    manifest.json
    <session-id>.json
```

Shared UI primitives live in `lib/` with their own prefixed stylesheet (e.g.
`rangeSlider.js` + `rangeSlider.css`, prefix `rs-`). The time-window control on both
heatmaps is `createRangeSlider`; a heatmap keeps its own `winStart`/`winEnd` state,
re-bins over the window in JS, and re-normalizes color intensity to the busiest bin
within the window (so narrowing drills in with its own contrast).

Session clustering: `scales.clusterByGap(events, thresholdMs)` splits events into
"sessions" wherever the inter-event gap exceeds the threshold. `createClusterBar` renders
those as buttons (plus a gap-threshold selector, default 30 min, and "All"); picking one
calls back with `[startMs, endMs]`. Each heatmap routes the cluster pick, the range
slider, and "All" through a single `setWindow(start, end)` that updates state, syncs the
slider handles, highlights the active session, and redraws — so the controls stay
consistent. Each view clusters its own events.

## Component contract

Every visualization is a module that exports:

```js
export function render(container, data, options = {}) { /* build DOM/SVG inside container */ }
```

and registers itself by `kind` in `src/components/registry.js`:

```js
register("file_heatmap", render);
```

Each component renders its SPEC section name as an `<h3>` title at the top of its output
(e.g. "File edit heatmap"), so the displayed title tracks the spec.

Composition: a session's JSON lists `views`, each with a `kind`. The shell looks up
`registry[kind]` and calls its `render` into a panel. **Adding a visualization = add
one component module + one `register(...)` line.** Nothing else changes.

## Generated-file marker

Every generated file begins with a header pointing back to its spec section, e.g.:

```js
// GENERATED from viz/SPEC.md — section "File edit heatmap".
// Do not hand-edit; edit the spec and regenerate.
```

## Data contract (the JSON boundary)

The Python side writes into `viz/data/`.

`manifest.json` — the sessions the shell can open:

```json
{
  "sessions": [
    { "id": "rkthomps__lean-time-m__880d1ca", "title": "rkthomps/lean-time-m @ 880d1ca",
      "owner": "rkthomps", "repo": "lean-time-m", "sha": "880d1ca...", "file": "rkthomps__lean-time-m__880d1ca.json" }
  ]
}
```

`<session-id>.json` — one session, holding one or more views. Each view is
`{ "kind": ..., "data": <kind-specific object> }`; the shell renders it by looking up
`registry[kind]` and calling `render(panel, view.data)`.

```json
{
  "session": { "owner": "rkthomps", "repo": "lean-time-m", "sha": "880d1ca..." },
  "views": [ { "kind": "file_heatmap", "data": { "file_data": [ "..." ] } } ]
}
```

Each view's `kind` must match a registered component. Per-kind `data` shapes:

### `file_heatmap`

`data` is exactly a serialized `FileHeatmapInfo` (from
`lean_edits_analysis.visualize.utils`):

```json
{
  "file_data": [
    { "file": "LeanTimeM/TimeM.lean",
      "change_events": [
        { "characters_added": 3, "characters_removed": 0, "time": "2026-02-23T10:08:56.886000" }
      ] }
  ]
}
```

`get_file_heatmap_info(...) -> FileHeatmapInfo` already produces this object; the
emitter just drops it in as the view's `data`. The component derives the time range and
**bins events into time columns in JS**, so the bin-size slider works without re-running
Python. The metric is **characters** (`characters_added` / `characters_removed`), not
lines.

### `decl_heatmap`

`data` is exactly a serialized `DeclHeatmapInfo` (from
`lean_edits_analysis.visualize.decl_heat_map`):

```json
{
  "file_data": [
    { "file": "LeanTimeM/TimeM.lean",
      "decl_changes": [
        { "decl": {
            "range": { "start": { "line": 73, "character": 0 }, "end": { "line": 78, "character": 15 } },
            "content": "...",
            "info": { "kind": "def", "name": "ListInput" } },
          "change_events": [
            { "characters_added": 1, "characters_removed": 0, "time": "2026-02-23T10:08:59.679000" }
          ] }
      ] }
  ]
}
```

`file_data` is sorted by file name and each `decl_changes` by `decl.range.start.line` on
the Python side, but the component also orders files by name and decls by start line so
the spec's source order holds even if a given data file isn't sorted. It shows only decls
with **≥ 2 `change_events`**, groups them under collapsible file headers, and shares one
wall-clock time axis across all files (binning in JS). When a time window is active it
further hides decls with no event inside the window (dropping file groups left empty),
recomputed each draw. `decl.info.name` may be `"[anonymous]"` — fall back to a
`kind @ Lline` label. Metric is **characters**.

## Python side

- Keep emitters pure: input is analysis output, output is JSON. No HTML, no drawing.
- Emitters live in `src/lean_edits_analysis/visualize/`. One function per view kind.
- A small CLI builds `viz/data/` for a given `(owner, repo, sha)` and updates
  `manifest.json`.

## Dev workflow

Browsers block `fetch()` over `file://`. To view locally:
`cd viz && python -m http.server`, then open the printed URL.

## Applying a SPEC change (agent procedure)

1. Read the changed entry in `SPEC.md`.
2. Find the file named in its **Component file** line; regenerate that module to match
   the prose.
3. If **Data it uses** changed, update the matching Python emitter and the per-kind
   shape above to match.
4. Keep `registry.js` in sync. Do not touch unrelated components.
5. Re-read `SPEC.md` to confirm nothing else depends on the changed behavior.

## Future host: VSCode webview (not built yet)

Keep components free of anything a webview lacks: no network calls, no `file://`
assumptions, and receive all data through the injected `data` argument rather than
fetching it themselves where avoidable. When the time comes, the extension will feed
the same session JSON to the same components via `postMessage`. **Do not build this
now** — just don't paint us into a corner.
