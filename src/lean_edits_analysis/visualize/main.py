import logging
import click
from pydantic import BaseModel
from pathlib import Path

from edit_data.types import WorkspaceChangeHistory

from lean_edits_analysis.data import load_matching_commit_sessions
from lean_edits_analysis.util import git_url_parts_from_session
from lean_edits_analysis.scratchpad import Scratchpad
from lean_edits_analysis.edit_info import EditInfoCache

from lean_edits_analysis.visualize.build import write_session_data
from lean_edits_analysis.visualize.file_heat_map import FileHeatmapInfo
from lean_edits_analysis.visualize.decl_heat_map import DeclHeatmapInfo


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


def file_heatmap_data(
    workspace_change_history: WorkspaceChangeHistory,
    scratchpad: Scratchpad,
    output_path: Path,
) -> FileHeatmapInfo:
    change_events = FileHeatmapInfo.build(workspace_change_history, scratchpad)
    with open(output_path, "w") as fout:
        fout.write(change_events.model_dump_json())
    return change_events


def decl_heatmap_data(
    workspace_change_history: WorkspaceChangeHistory,
    scratchpad: Scratchpad,
    output_path: Path,
):
    change_events = DeclHeatmapInfo.build(workspace_change_history, scratchpad)
    with open(output_path, "w") as fout:
        fout.write(change_events.model_dump_json())
    return change_events


@click.command()
@click.argument("repo_owner", type=str)
@click.argument("repo_name", type=str)
@click.argument("commit_sha", type=str)
def main(
    repo_owner: str,
    repo_name: str,
    commit_sha: str,
):
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    logging.getLogger("lean_edits_analysis").setLevel(logging.INFO)
    logging.getLogger("__name__").setLevel(logging.INFO)

    session = load_matching_commit_sessions(
        repo_owner=repo_owner,
        repo_name=repo_name,
        commit_sha=commit_sha,
    )

    git_url_parts = git_url_parts_from_session(session)
    assert (
        git_url_parts is not None
    ), "Failed to parse git URL parts from session metadata."

    scratchpad = Scratchpad(
        repo_owner=git_url_parts.owner,
        repo_name=git_url_parts.repo,
        commit_sha=commit_sha,
    )

    file_heatmap = file_heatmap_data(
        workspace_change_history=session,
        scratchpad=scratchpad,
        output_path=Path("file_heatmap_data.json"),
    )
    decl_heatmap = decl_heatmap_data(
        workspace_change_history=session,
        scratchpad=scratchpad,
        output_path=Path("decl_heatmap_data.json"),
    )
    write_session_data(
        owner=git_url_parts.owner,
        repo=git_url_parts.repo,
        sha=commit_sha,
        file_heatmap=file_heatmap,
        decl_heatmap=decl_heatmap,
    )


if __name__ == "__main__":
    main()
