# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Analyzes fine-grained edit data collected from Lean 4 users. The raw data is uploaded by the `edit-data` package (https://github.com/rkthomps/edit-data) and synced from S3.

## Commands

- Install / sync deps: `uv sync` (Python >=3.14, managed by `uv`)
- Run a script: `uv run python -m lean_edits_analysis.analysis` or `uv run python -m lean_edits_analysis.analyze_session`
- Console entrypoint: `uv run lean-edits-analysis` (currently a stub `main()` in `__init__.py`)
- Type-check: `uv run pyright`
- Pull data from S3: `./sync.sh` (requires `aws` CLI with credentials configured; mirrors `s3://programming-vacuum` → `data/` with `--delete`)

There is no test suite.

## Data layout

`data/` (gitignored) holds the synced uploads. Layout: `data/<workspace>/<commit-sha>/<timestamp>.zip`. For each commit, only the **latest timestamp** zip is processed (see `load_all_workspace_histories` and `load_last_commit_history`). Top-level `.zip` files directly under `<workspace>/` are legacy and skipped.

`scratchpad/` (gitignored) is where `Scratchpad` clones the corresponding upstream repos at the recorded commit SHA and runs `lake update` / `lake build` to reproduce the build context for analysis.

## Architecture

The core domain object is `WorkspaceChangeHistory` from the external `edit-data` package — load it via `edit_data.zip_edits.load_workspace_history(zip_path)`. Each history has `.metadata` (either `LocalChangeMetadata` or `GitChangeMetadata` with `remotes` and `head`) and `.files` (list of file change histories with `.edits_history`).

A "programming session" (per `TODO.md`) = all work on one GitHub commit. Local-only metadata and commits without an `origin` remote URL are filtered out (`workspace_histories_by_commit` in `analysis.py`); remaining histories are keyed by `Commit(Repo(owner, name), sha)`. `parse_github_url` handles both SSH (`git@github.com:owner/repo.git`) and HTTPS forms.

Two entrypoints exist with overlapping concerns:
- `analysis.py` — aggregate stats across all histories under `data/`. Defines its own `DATA_LOC = Path("data")`.
- `analyze_session.py` — drill into a single `(owner, repo, sha)` session, also instantiates a `Scratchpad` to clone+build that commit. Imports `DATA_LOC` from `common.py`.

`common.py` is the canonical place for shared paths (`DATA_LOC`, `SCRATCHPAD_LOC`); the duplicate constant in `analysis.py` is a known inconsistency.

`TODO.md` lists the in-progress analysis goals: per-session changed files / edit counts, added-removed-modified top-level declarations, and which declarations changed (`ChangedDeclarations` dataclass is the stub for this in `analyze_session.py`).
