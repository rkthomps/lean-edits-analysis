"""FastAPI server: serves the viz static app and provides on-demand diff computation."""

from pathlib import Path

import click
import uvicorn
from functools import cache
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from edit_data.types import (
    ConcreteCheckpoint,
    FileChangeHistory,
    NewConcreteCheckpoint,
    SameConcreteCheckpoint,
    WorkspaceChangeHistory,
)
from edit_data.edits import apply_change

from lean_edits_analysis.data import load_matching_commit_sessions

VIZ_DIR = Path("viz")

app = FastAPI()

_session_cache: dict[tuple[str, str, str], WorkspaceChangeHistory] = {}


def _load_session(owner: str, repo: str, sha: str) -> WorkspaceChangeHistory:
    key = (owner, repo, sha)
    if key not in _session_cache:
        _session_cache[key] = load_matching_commit_sessions(owner, repo, sha)
    return _session_cache[key]


def _resolve_checkpoint(checkpoint: ConcreteCheckpoint) -> str:
    if isinstance(checkpoint, NewConcreteCheckpoint):
        return checkpoint.contents
    assert isinstance(checkpoint, SameConcreteCheckpoint)
    return _resolve_checkpoint(checkpoint.prev)


def _file_history(session: WorkspaceChangeHistory, file: str) -> FileChangeHistory:
    file_dict = session.get_dict()
    key = Path(file)
    if key not in file_dict:
        raise HTTPException(status_code=404, detail=f"File {file!r} not in session")
    return file_dict[key]


@app.get("/api/diff/{owner}/{repo}/{sha}")
async def get_diff(owner: str, repo: str, sha: str, file: str, edit_index: int):
    try:
        session = _load_session(owner, repo, sha)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    history = _file_history(session, file)

    if edit_index < 0 or edit_index >= len(history.edits_history):
        raise HTTPException(
            status_code=400,
            detail=f"edit_index {edit_index} out of range (0–{len(history.edits_history) - 1})",
        )

    edit = history.edits_history[edit_index]
    before = _resolve_checkpoint(edit.base_change)
    after = before
    for change in edit.changes:
        after = apply_change(after, change)

    return {
        "file": file,
        "time": edit.time.isoformat(),
        "before": before,
        "after": after,
        "changes": [
            {
                "rangeOffset": c.rangeOffset,
                "rangeLength": c.rangeLength,
                "text": c.text,
            }
            for c in edit.changes
        ],
    }


# Static files mount last — catches everything not matched by an API route above.
app.mount("/", StaticFiles(directory=str(VIZ_DIR), html=True), name="viz")


@click.command()
@click.option("--host", default="0.0.0.0", help="Bind host")
@click.option("--port", default=8080, type=int, help="Bind port")
def run(host: str, port: int):
    """Start the viz FastAPI server. Run from the project root."""
    uvicorn.run("lean_edits_analysis.visualize.server:app", host=host, port=port)
