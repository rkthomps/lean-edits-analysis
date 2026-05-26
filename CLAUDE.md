# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Analyzes fine-grained edit data collected from Lean 4 users by the [LeanEdits](https://marketplace.visualstudio.com/items?itemName=KyleThompson.lean-edits) VS Code extension. The pipeline has three stages:

1. **Download** raw edit data from S3 (`sync.sh`).
2. **Replay** each edit against a reproduced build environment and cache the Lean diagnostics + declarations after every edit (`EditInfo`).
3. **Visualize** edit sessions in a static, dependency-free web app under `viz/`.

The raw zip format is produced by the external [`edit-data`](https://github.com/rkthomps/edit-data) package; Lean LSP interaction goes through [`lean-client`](https://github.com/rkthomps/lean-client) (both are git dependencies).

## Commands

- Install / sync deps: `uv sync` (Python >=3.14, managed by `uv`)
- Type-check: `uv run pyright`
- Pull data from S3: `./sync.sh` (requires `aws` CLI with credentials configured; mirrors `s3://programming-vacuum` → `data/` with `--delete`)

Console entry points (declared in `pyproject.toml`):

- `uv run lean-edits-analysis` — stub `main()` in `__init__.py`.
- `uv run cache-edits repo <owner> <name>` — replay edits for one repo and write `EditInfo` caches.
- `uv run cache-edits everything` — list metadata for every cached repo / session.
- `uv run viz-edits commit <owner> <name> <sha>` — build viz JSON for one commit (assumes cache exists).
- `uv run viz-edits show` — emit viz JSON for every already-cached session.
- `uv run viz-edits cache-and-show [--workers N]` — full pipeline: cache then emit viz JSON for every discovered session, with per-repo logs under `logs/`.

Viewing the viz app locally (browsers block `fetch()` over `file://`): `cd viz && python -m http.server`, then open the printed URL.

There is no test suite.

## Directory layout

Top-level, gitignored unless noted:

- `data/` — synced uploads. Layout: `data/<workspace>/<commit-sha>/<timestamp>.zip`. Only the **latest timestamp** per commit is processed (see `load_last_commit_history` in `data.py`). Top-level `.zip` files directly under `<workspace>/` are legacy and skipped.
- `scratchpad/` — `Scratchpad` clones each upstream repo at the recorded commit SHA here, patches in [`llm-instruments`](https://github.com/rkthomps/llm-instruments), and runs `lake update` / `lake build` to reproduce the build context.
- `cache/` — per-edit `EditInfo` cache. Layout: `cache/<owner>/<repo>/<sha>/<file>/{prev_edit_info.json, edit_infos.jsonl}`.
- `locks/` — `filelock` files used to serialize scratchpad work per repo (`locks/<owner>/<repo>/repo.lock`).
- `logs/` — log files from `viz-edits cache-and-show`.
- `viz/data/` — JSON consumed by the viz app: `manifest.json` plus one `<session-id>.json` per session.

## Python package layout (`src/lean_edits_analysis/`)

- `common.py` — canonical shared paths (`DATA_LOC`, `SCRATCHPAD_LOC`).
- `analysis.py` — standalone aggregate stats (#repos / #commits / #edits) over `data/`. Has its own copy of `DATA_LOC` and its own `parse_github_url` / `Repo` / `Commit` types — overlaps with `util.py` and is a known inconsistency (the rest of the code uses `util.git_parts_from_metadata` and `GitUrlParts`).
- `data.py` — loaders that walk `data/`: `load_last_commit_history`, `load_matching_sessions`, `load_matching_commit_sessions`, plus the `RepoMetadata` / `SessionMetadata` summaries used by the CLIs.
- `util.py` — shared helpers: `GitUrlParts.from_url` (handles HTTPS and SSH), `git_parts_from_metadata`, `git_url_parts_from_session`, `count_session_edits`, `to_client_range`.
- `scratchpad.py` — `Scratchpad(owner, repo, sha)`: clone + checkout, inject the `llm-instruments` require into `lakefile.toml` or `lakefile.lean`, `lake update llm-instruments`, `lake build`. `_get_compatible_version` maps a `lean-toolchain` string to the right `llm-instruments` branch.
- `edit_info.py` — the replay-and-cache core.
  - `EditInfo` = `{diagnostics, decls}` after one edit, gathered via `LeanClient` (`FindDeclsRequest` + `wait_for_diagnostics`).
  - `iter_edits_with_info` walks one file's edit history, materializing each version onto the scratchpad and pulling fresh `EditInfo` from Lean. Restarts the client when an edit changes more than one file (otherwise just `change_file`).
  - `EditInfoCache` persists per-(repo, sha, file) caches and supports incremental resumption.
  - Click CLI: `cache-edits repo <owner> <name>` and `cache-edits everything`.
- `visualize/` — viz JSON emitters and the CLI behind `viz-edits`.
  - `build.py` — pure data step. Writes a `<session-id>.json` (a `SessionData` with one or more `views`) and upserts `viz/data/manifest.json`. **No HTML, no rendering.**
  - `file_heat_map.py` — `FileHeatmapInfo`: per-file `(characters_added, characters_removed, time)` events. Does not need the `EditInfo` cache.
  - `decl_heat_map.py` — `DeclHeatmapInfo`: per-declaration change events, computed by intersecting each `ContentChange` against `prev_info.decls` from the cache. **Requires the `EditInfo` cache.**
  - `main.py` — Click CLI (`commit` / `show` / `cache-and-show`).

## Domain model

The core domain object is `WorkspaceChangeHistory` from `edit-data` — load it via `edit_data.zip_edits.load_workspace_history(zip_path)`. Each history has:

- `.metadata`: either `LocalChangeMetadata` (skipped) or `GitChangeMetadata` (`remotes`, `head`).
- `.files`: list of file change histories, each with `.edits_history` (a list of `Edit`s; each `Edit` has `.changes`, a list of `ContentChange` with LSP-style range + offset).

A **programming session** = all work on one GitHub commit (see `TODO.md`). Sessions are filtered: local-only metadata and metadata with no usable `origin` remote URL are dropped. Surviving sessions are keyed by `(owner, repo, sha)`.

## Viz subsystem (`viz/`)

A vanilla-JS, no-build, no-dependency, no-CDN ES-module app. The host is `viz/index.html`; components live under `viz/src/components/`. **Treat `viz/SPEC.md` as the source of truth for *what* the visualizations are, and `viz/CONVENTIONS.md` as the rulebook for *how* they are built** (data/component/shell layers separated by the JSON boundary, prefixed CSS classes, generated-file headers, etc.). The Python `visualize/` package and the JS components communicate **only** through the JSON files in `viz/data/`; per-kind shapes are documented in `viz/CONVENTIONS.md`.

When changing a visualization, edit `SPEC.md` and regenerate the matching component — do not hand-edit generated JS.

## TODOs

`TODO.md` lists open analysis goals: per-session changed files / edit counts, added-removed-modified top-level declarations, and which declarations changed.
