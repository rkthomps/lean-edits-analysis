from typing import Iterable

import re
import logging
from urllib.parse import urlparse
from dataclasses import dataclass
from pathlib import Path

from edit_data.types import (
    WorkspaceChangeHistory,
    LocalChangeMetadata,
    GitChangeMetadata,
    Remote,
)
from edit_data.zip_edits import load_workspace_history

DATA_LOC = Path("data")

logger = logging.getLogger(__name__)

"""
Dashboard information:

- Number of github repos
  - Number of commits
    - Number of edits
"""


def parse_github_url(url: str) -> tuple[str, str]:
    # SSH: git@github.com:owner/repo.git
    ssh_match = re.match(r"git@github\.com:([^/]+)/(.+?)(?:\.git)?$", url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)

    # HTTPS: https://github.com/owner/repo
    path = urlparse(url).path
    parts = path.strip("/").split("/")
    return parts[0], parts[1]


@dataclass(frozen=True, eq=True)
class Repo:
    owner: str
    name: str


@dataclass(frozen=True, eq=True)
class Commit:
    repo: Repo
    sha: str


def load_all_workspace_histories(data_loc: Path) -> Iterable[WorkspaceChangeHistory]:
    for workspace_changes in data_loc.iterdir():
        for commit_changes in workspace_changes.iterdir():
            if commit_changes.is_file():
                if commit_changes.suffix == ".zip":
                    logger.info(f"Skipping legacy zip file: {commit_changes}")
                else:
                    logger.info(f"Skipping unknown file: {commit_changes}")
            else:
                commit_uploads = list(commit_changes.iterdir())
                # We will process the latest upload for each commit.
                # The filenames for the uploads are e.g. 1773698868387.zip
                # We can take the file with the largest timestamp as the latest upload.
                if len(commit_uploads) == 0:
                    continue
                latest_upload = max(commit_uploads, key=lambda p: int(p.stem))
                logger.info(f"Loading workspace history from {latest_upload}")
                try:
                    yield load_workspace_history(latest_upload)
                except Exception as e:
                    logger.error(
                        f"Failed to load workspace history from {latest_upload}: {e}"
                    )


def num_edits(workspace_history: WorkspaceChangeHistory) -> int:
    num_edits = 0
    for fch in workspace_history.files:
        for edit in fch.edits_history:
            if len(edit.changes) > 0:
                num_edits += 1
    return num_edits


def find_origin_remote(metadata: GitChangeMetadata) -> Remote | None:
    for remote in metadata.remotes:
        if remote.name == "origin":
            return remote
    return None


def get_remote_url(remote: Remote) -> str | None:
    if remote.fetch_url is not None:
        return remote.fetch_url
    if remote.push_url is not None:
        return remote.push_url
    return None


def workspace_histories_by_commit(
    workspace_histories: Iterable[WorkspaceChangeHistory],
) -> dict[Commit, WorkspaceChangeHistory]:
    result: dict[Commit, WorkspaceChangeHistory] = {}
    for workspace_history in workspace_histories:
        if isinstance(workspace_history.metadata, LocalChangeMetadata):
            logger.info(
                f"Skipping local edits: {workspace_history.metadata.workspace_name}"
            )
            continue
        origin_remote = find_origin_remote(workspace_history.metadata)
        if origin_remote is None:
            logger.info(
                f"Skipping commit with no origin remote: {workspace_history.metadata.remotes}"
            )
            continue
        remote_url = get_remote_url(origin_remote)
        if remote_url is None:
            logger.info(
                f"Skipping commit with origin remote with no URL: {origin_remote}"
            )
            continue
        owner, repo_name = parse_github_url(remote_url)
        repo = Repo(owner=owner, name=repo_name)
        commit = Commit(repo=repo, sha=workspace_history.metadata.head)
        result[commit] = workspace_history
    return result


def analyze_workspace_histories(workspace_histories: Iterable[WorkspaceChangeHistory]):

    histories_by_commit = workspace_histories_by_commit(workspace_histories)
    print(f"Number of commits: {len(histories_by_commit)}")
    repos = set(commit.repo for commit in histories_by_commit.keys())
    print(f"Number of repos: {len(repos)}")
    edits = sum(num_edits(history) for history in histories_by_commit.values())
    print(f"Number of edits: {edits}")

    by_repo: dict[Repo, dict[Commit, WorkspaceChangeHistory]] = {}
    for commit, history in histories_by_commit.items():
        if commit.repo not in by_repo:
            by_repo[commit.repo] = {}
        by_repo[commit.repo][commit] = history

    for repo, commits in by_repo.items():
        print(f"Repo {repo}: {len(commits)} commits")
        for commit, history in commits.items():
            print(f"  Commit {commit.sha}: {num_edits(history)} edits")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    workspace_histories = load_all_workspace_histories(DATA_LOC)
    analyze_workspace_histories(workspace_histories)
