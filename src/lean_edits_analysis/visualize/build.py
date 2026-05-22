"""Emit the JSON the viz app reads (viz/data/).

The emitter is a pure data step: it takes the analysis objects (a ``FileHeatmapInfo``
and/or a ``DeclHeatmapInfo``) plus session identity, and writes a per-session JSON file
holding one view per visualization, then upserts ``manifest.json``. No HTML, no
rendering — see ``viz/CONVENTIONS.md`` for the data contract.
"""

import logging
from typing import Literal, Union, Annotated

import json
from pydantic import BaseModel, Field
from pathlib import Path

from lean_edits_analysis.visualize.file_heat_map import FileHeatmapInfo
from lean_edits_analysis.visualize.decl_heat_map import DeclHeatmapInfo

logger = logging.getLogger(__name__)

VIZ_DATA_LOC = Path("viz/data")


class SessionManifest(BaseModel):
    owner: str
    repo: str
    sha: str

    @property
    def id(self) -> str:
        return f"{self.owner}__{self.repo}__{self.sha[:7]}"

    @property
    def title(self) -> str:
        return f"{self.owner}/{self.repo} @ {self.sha[:7]}"

    @property
    def file_name(self) -> str:
        return f"{self.id}.json"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "owner": self.owner,
            "repo": self.repo,
            "sha": self.sha,
            "file": self.file_name,
        }


class Manifest(BaseModel):
    sessions: list[SessionManifest]

    def to_dict(self) -> dict:
        return {"sessions": [session.to_dict() for session in self.sessions]}


class FileHeatmapView(BaseModel):
    kind: Literal["file_heatmap"] = "file_heatmap"
    data: FileHeatmapInfo


class DeclHeatmapView(BaseModel):
    kind: Literal["decl_heatmap"] = "decl_heatmap"
    data: DeclHeatmapInfo


SessionView = Annotated[
    Union[FileHeatmapView, DeclHeatmapView],
    Field(discriminator="kind"),
]


class SessionData(BaseModel):
    session: SessionManifest
    views: list[SessionView]


def _to_session_data(
    owner: str,
    repo: str,
    sha: str,
    file_heatmap: FileHeatmapInfo | None = None,
    decl_heatmap: DeclHeatmapInfo | None = None,
) -> SessionData:
    views: list[SessionView] = []
    if file_heatmap is not None:
        views.append(FileHeatmapView(data=file_heatmap))
    if decl_heatmap is not None:
        views.append(DeclHeatmapView(data=decl_heatmap))

    session_manifest = SessionManifest(owner=owner, repo=repo, sha=sha)
    return SessionData(session=session_manifest, views=views)


def _update_manifest(out_dir: Path) -> None:
    session_manifests: list[SessionManifest] = []
    for f in out_dir.glob("*.json"):
        if f.name == "manifest.json":
            continue
        try:
            session_data = SessionData.model_validate_json(f.read_text())
            session_manifests.append(session_data.session)
        except Exception as e:
            logger.warning(f"Failed to parse session data from {f}: {e}")
    session_manifests.sort(key=lambda s: s.id)
    manifest = Manifest(sessions=session_manifests)
    manifest_loc = out_dir / "manifest.json"
    with open(manifest_loc, "w") as fout:
        fout.write(json.dumps(manifest.to_dict()))
    logger.info(f"Wrote manifest to {manifest_loc}")


def write_session_data(
    owner: str,
    repo: str,
    sha: str,
    file_heatmap: FileHeatmapInfo | None = None,
    decl_heatmap: DeclHeatmapInfo | None = None,
    out_dir: Path = VIZ_DATA_LOC,
):
    session_data = _to_session_data(
        owner=owner,
        repo=repo,
        sha=sha,
        file_heatmap=file_heatmap,
        decl_heatmap=decl_heatmap,
    )
    out_loc = out_dir / session_data.session.file_name
    out_loc.parent.mkdir(parents=True, exist_ok=True)
    with open(out_loc, "w") as fout:
        fout.write(session_data.model_dump_json(indent=2))
    logger.info(f"Wrote session data to {out_loc}")
    _update_manifest(out_dir)
