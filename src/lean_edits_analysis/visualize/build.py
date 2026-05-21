"""Emit the JSON the viz app reads (viz/data/).

The emitter is a pure data step: it takes the analysis objects (a ``FileHeatmapInfo``
and/or a ``DeclHeatmapInfo``) plus session identity, and writes a per-session JSON file
holding one view per visualization, then upserts ``manifest.json``. No HTML, no
rendering — see ``viz/CONVENTIONS.md`` for the data contract.
"""

import json
from pathlib import Path

from lean_edits_analysis.visualize.file_heat_map import FileHeatmapInfo
from lean_edits_analysis.visualize.decl_heat_map import DeclHeatmapInfo

VIZ_DATA_LOC = Path("viz/data")


def session_id(owner: str, repo: str, sha: str) -> str:
    return f"{owner}__{repo}__{sha[:7]}"


def write_session_data(
    owner: str,
    repo: str,
    sha: str,
    *,
    file_heatmap: FileHeatmapInfo | None = None,
    decl_heatmap: DeclHeatmapInfo | None = None,
    title: str | None = None,
    out_dir: Path = VIZ_DATA_LOC,
) -> Path:
    """Write ``<session-id>.json`` and upsert ``manifest.json``. Returns the session file path.

    Each provided heatmap becomes one view (in this order: file, then decl).
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    sid = session_id(owner, repo, sha)
    file_name = f"{sid}.json"

    views: list[dict] = []
    if file_heatmap is not None:
        views.append(
            {"kind": "file_heatmap", "data": json.loads(file_heatmap.model_dump_json())}
        )
    if decl_heatmap is not None:
        views.append(
            {"kind": "decl_heatmap", "data": json.loads(decl_heatmap.model_dump_json())}
        )

    session = {
        "session": {"owner": owner, "repo": repo, "sha": sha},
        "views": views,
    }
    (out_dir / file_name).write_text(json.dumps(session, indent=2))

    _upsert_manifest(
        out_dir,
        {
            "id": sid,
            "title": title or f"{owner}/{repo} @ {sha[:7]}",
            "owner": owner,
            "repo": repo,
            "sha": sha,
            "file": file_name,
        },
    )
    return out_dir / file_name


def _upsert_manifest(out_dir: Path, entry: dict) -> None:
    manifest_path = out_dir / "manifest.json"
    manifest: dict = {"sessions": []}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())

    sessions = [s for s in manifest.get("sessions", []) if s.get("id") != entry["id"]]
    sessions.append(entry)
    sessions.sort(key=lambda s: s["id"])
    manifest_path.write_text(json.dumps({"sessions": sessions}, indent=2))
