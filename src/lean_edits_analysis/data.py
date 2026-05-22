import logging
from dataclasses import dataclass
from typing import Iterable
from pathlib import Path

from edit_data.types import (
    GitChangeMetadata,
    WorkspaceChangeHistory,
)
from edit_data.zip_edits import load_workspace_history

from lean_edits_analysis.common import DATA_LOC
from lean_edits_analysis.util import git_parts_from_metadata, count_session_edits

logger = logging.getLogger(__name__)


def get_changed_files(
    workspace_change_history: WorkspaceChangeHistory,
) -> Iterable[tuple[Path, int]]:
    """
    Returns an iterable of tuples containing file paths and the number of edits in each file.
    The number of edits must be non-zero.
    """
    for file in workspace_change_history.files:
        if 0 < len(file.edits_history):
            yield file.path, len(file.edits_history)


def load_last_commit_history(commit_data_path: Path) -> WorkspaceChangeHistory:
    commit_uploads = list(commit_data_path.iterdir())
    if len(commit_uploads) == 0:
        raise ValueError(f"No uploads found for commit data path: {commit_data_path}")
    latest_upload = max(commit_uploads, key=lambda p: int(p.stem))
    return load_workspace_history(latest_upload)


def get_repo_commits(repo_owner: str, repo_name: str) -> list[str]:
    commits: list[str] = []
    for workspace_data in DATA_LOC.iterdir():
        if repo_owner not in workspace_data.name:
            continue
        if repo_name not in workspace_data.name:
            continue
        for commit_data in workspace_data.iterdir():
            commits.append(commit_data.name)
    return commits


def load_matching_commit_sessions(
    repo_owner: str, repo_name: str, commit_sha: str
) -> WorkspaceChangeHistory:
    for workspace_data in DATA_LOC.iterdir():
        if repo_owner not in workspace_data.name:
            continue
        if repo_name not in workspace_data.name:
            continue
        for commit_data in workspace_data.iterdir():
            if commit_sha not in commit_data.name:
                continue
            return load_last_commit_history(commit_data)
    raise ValueError(
        f"No session found for repo {repo_owner}/{repo_name} at commit {commit_sha}"
    )


def load_matching_sessions(
    repo_owner: str, repo_name: str
) -> Iterable[WorkspaceChangeHistory]:
    for workspace_data in DATA_LOC.iterdir():
        if repo_owner not in workspace_data.name:
            continue
        if repo_name not in workspace_data.name:
            continue
        for commit_data in workspace_data.iterdir():
            try:
                yield load_last_commit_history(commit_data)
            except Exception as e:
                logger.warning(
                    f"Failed to load session for repo {repo_owner}/{repo_name} at commit {commit_data.name}. Error: {e}"
                )


@dataclass
class SessionMetadata:
    head: str
    edits: int


@dataclass
class RepoMetadata:
    repo_owner: str
    repo_name: str
    sessions: list[SessionMetadata]

    @property
    def total_edits(self) -> int:
        return sum(session.edits for session in self.sessions)

    @property
    def total_sessions(self) -> int:
        return len(self.sessions)


def find_repo_metadata() -> list[RepoMetadata]:
    repos: dict[tuple[str, str], list[SessionMetadata]] = {}
    for workspace_data in DATA_LOC.iterdir():
        for commit_data in workspace_data.iterdir():
            sessions: list[SessionMetadata] = []
            try:
                session = load_last_commit_history(commit_data)
            except Exception as e:
                logger.warning(
                    f"Failed to load session for workspace {workspace_data.name} at commit {commit_data.name}. Error: {e}"
                )
                continue
            if not isinstance(session.metadata, GitChangeMetadata):
                logger.warning(
                    f"Skipping session for edits at workspace {session.metadata.workspace_name}. Local metadata."
                )
                continue
            git_parts = git_parts_from_metadata(session.metadata)
            if git_parts is None:
                logger.warning(
                    f"Skipping session for edits at workspace {session.metadata.workspace_name}. Unable to parse git parts from metadata."
                )
                continue
            num_edits = count_session_edits(session)
            sessions.append(
                SessionMetadata(head=session.metadata.head, edits=num_edits)
            )
            repo_key = (git_parts.owner, git_parts.repo)
            if repo_key not in repos:
                repos[repo_key] = []
            repos[repo_key].extend(sessions)
    return [
        RepoMetadata(repo_owner=owner, repo_name=repo, sessions=sessions)
        for (owner, repo), sessions in repos.items()
    ]
