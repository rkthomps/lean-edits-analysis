from typing import Optional
import click
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

from edit_data.types import GitChangeMetadata

from lean_edits_analysis.data import load_matching_commit_sessions
from lean_edits_analysis.edit_info import EditInfoCache
from lean_edits_analysis.visualize.file_heat_map import FileHeatmapInfo
from lean_edits_analysis.visualize.diff import get_diff, DiffInfo
from lean_edits_analysis.util import git_parts_from_metadata


@click.group()
def cli():
    pass


def edit_diff(
    owner: str, repo: str, sha: str, file: Path, start_edit_idx: int, end_edit_idx: int
):
    session = load_matching_commit_sessions(owner, repo, sha)
    assert isinstance(session.metadata, GitChangeMetadata)
    git_parts = git_parts_from_metadata(session.metadata)
    assert (
        git_parts is not None
    ), f"Expected Git metadata for session, got {session.metadata}"
    cache = EditInfoCache(
        scratchpad_repo_owner=git_parts.owner,
        scratchpad_repo_name=git_parts.repo,
        scratchpad_commit_sha=session.metadata.head,
        file=file,
    )


@dataclass
class ChangedFileInfo:
    file: str
    edits_made: int
    first_edit_time: Optional[datetime]
    last_edit_time: Optional[datetime]
    num_characters_added: int
    num_characters_removed: int


@cli.command()
@click.option("--owner", required=True, help="GitHub repository owner")
@click.option("--repo", required=True, help="GitHub repository name")
@click.option("--sha", required=True, help="GitHub commit SHA")
def changed_files(owner: str, repo: str, sha: str):
    session = load_matching_commit_sessions(owner, repo, sha)
    heatmap_info = FileHeatmapInfo.build(session)
    results: list[ChangedFileInfo] = []
    for fce in heatmap_info.file_data:
        events = fce.change_events
        results.append(
            ChangedFileInfo(
                file=str(fce.file),
                edits_made=len(events),
                first_edit_time=min(e.time for e in events) if events else None,
                last_edit_time=max(e.time for e in events) if events else None,
                num_characters_added=sum(e.characters_added for e in events),
                num_characters_removed=sum(e.characters_removed for e in events),
            )
        )
    for r in results:
        click.echo(
            f"{r.file}: {r.edits_made} edits, "
            f"+{r.num_characters_added}/-{r.num_characters_removed} chars, "
            f"{r.first_edit_time} → {r.last_edit_time}"
        )


if __name__ == "__main__":
    cli()
