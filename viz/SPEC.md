# Visualizations

This file describes the visualizations for the Lean edit data — what each one shows
and how it behaves. **It is the source of truth.** The app under `viz/` is generated
from this file.

To change a visualization, edit the plain-language description here and then ask an
agent to regenerate the app. You should never need to edit the JavaScript yourself.
(The technical rules an agent follows live in `CONVENTIONS.md` — you don't need to
read that.)

## How it works, briefly

The Python analysis writes out data files. The app reads them and draws each
visualization. You open the app, pick a session to look at, and each session shows one
or more visualizations.

## The site

- **Session page** — pick a session (one programming session = all the work on one
  commit). Shows the visualizations for that session, starting with the file edit
  heatmap below.
- **File page** *(planned)* — drill into a single file: how its declarations changed
  over time, with a slider to scrub through the edit history.

### Sidebar navigation

The sidebar lists sessions as a three-level hierarchy: repo owner → repo → commit.
Each level is annotated with the total edit count and (for repos and commits) the last
modified date. Owners are sorted by total edits descending; repos within an owner and
commits within a repo are sorted by last modified date descending (most recent first).
Selecting a commit loads that session and scrolls the main panel back to the top, so
the results are always visible without having to scroll up.

## Writing a visualization

Each visualization is one section below, using the same headings every time:

- **What it shows** — the idea, in a sentence or two.
- **Data it uses** — what information it needs (an agent wires this up).
- **Layout** — how it's arranged on screen.
- **Color** — what the colors mean.
- **Interactions** — what happens when you hover, click, or drag.
- **Component file** — the generated file it maps to. *(an agent fills this in)*

To add a visualization, copy these headings into a new section and fill them in. To
change one, edit the prose under its headings.

---

## File edit heatmap

**What it shows.** For one programming session, which files were edited and when, and
how much. Each file gets a row showing the characters added and removed across the
session.

**Data it uses.** For each file, the list of edits with a timestamp and how many
characters that edit added and removed. (This is exactly the `FileHeatmapInfo` object
returned by `get_file_heatmap_info`.)

**Layout.** One row per file, stacked top to bottom, ordered by when each file was
first edited. Each row is split into two thin bands: the top band is characters added,
the bottom band is characters removed. The horizontal axis is real (wall-clock) time, divided
into equal time bins from the start to the end of the session. File names label the
left edge; time labels run along the bottom.

**Color.** The added band is green, the removed band is red. The more characters added
in a time bin, the stronger the green; the more removed, the stronger the red. Added
and removed are scaled independently — each against its own busiest bin — so both stay
visible even when one dominates. Bins with no activity stay blank.

**Interactions.** Hovering a cell shows the file, the exact time range of that bin, and
the number of characters added and removed. A "Time detail" slider changes how wide the
time bins are. A two-handle "Time window" slider sets the start and end of the time range
shown — it starts at the full session span; drag the handles inward to drill into a
sub-window, and "Reset" restores the full span. Narrowing the window re-bins and
re-colors over just that range. Edits are also auto-grouped into **sessions** by gaps in
activity (a configurable inactivity gap, default 30 minutes): a row of session buttons —
each showing its start time and edit count — zooms the window straight to that session,
and "All" zooms back out.

**Component file.** `viz/src/components/fileHeatmap.js` *(generated — don't edit)*

---

## Declaration edit heatmap

**What it shows.** A finer-grained version of the file heatmap: instead of one row per
file, one row per declaration (theorem, def, instance, …), showing the characters added
and removed to that declaration over the session. Only declarations edited in at least
two edits are shown. Declarations are grouped under their file, and each file group can
be collapsed.

**Data it uses.** For each file, its declarations (each with a kind, name, and source
location) and, per declaration, the list of edits that touched it with a timestamp and
how many characters that edit added and removed. (This is exactly the `DeclHeatmapInfo`
object returned by `DeclHeatmapInfo.build`.)

**Layout.** Files are listed in name order, each as a collapsible group with a clickable
header (declaration count, expand/collapse). Within a file, declarations are in source
order (top of file first). Each declaration is a row split into two thin bands — the top
band is characters added, the bottom band is characters removed. The horizontal axis is
real (wall-clock) time, shared across every file and declaration so the rows line up in
time; time labels run along the bottom. Declaration labels (kind + name) sit in the left
gutter; declarations with no name are labelled by kind and line, e.g. "def @ L74". When
the time window is narrowed (via the slider or a session button), declarations with no
edits inside the window are hidden, and any file left with no declarations drops out — so
a zoomed-in view shows only what was actually worked on then.

**Color.** Same as the file heatmap: green for added, red for removed, stronger with more
characters in a time bin. Added and removed are scaled independently against the busiest
declaration-bin shown, so both stay visible. Bins with no activity stay blank.

**Interactions.** Hovering a cell shows the declaration, its file, the time range of that
bin, and the characters added and removed. Clicking a file header collapses or expands
that file's declarations (files start expanded). A "Time detail" slider changes the
time-bin width, and a two-handle "Time window" slider sets the start and end of the range
shown so you can drill into a sub-window (it starts at the full span; "Reset" restores
it). Narrowing the window re-bins and re-colors over just that range. Edits are also
auto-grouped into **sessions** by gaps in activity (a configurable inactivity gap,
default 30 minutes): a row of session buttons zooms the window straight to a session, and
"All" zooms back out.

**Component file.** `viz/src/components/declHeatmap.js` *(generated — don't edit)*

---

## Planned visualizations

Not built yet — captured here so the ideas aren't lost:

- **Session summary** — which declarations were added, removed, or modified, and how
  many edits each one took.
- **Edits by declaration type** — where editing effort went, broken down by kind of
  declaration (theorem, def, instance, …).
- **History slider** *(File page)* — scrub through a file's edit history and see the
  Lean diagnostics at each point.
- **Ask about a session** — a chat that can jump to different points in the history and
  answer "what happened" during a task.
