from typing import Optional
import re
from dataclasses import dataclass

from edit_data.types import (
    GitChangeMetadata,
    Range as EditRange,
    Remote,
    WorkspaceChangeHistory,
)
from lean_client.client import Range, Position


def to_client_range(range: EditRange) -> Range:
    return Range(
        start=Position(line=range.start.line, character=range.start.character),
        end=Position(line=range.end.line, character=range.end.character),
    )


@dataclass
class GitUrlParts:
    hostname: str
    owner: str
    repo: str

    @classmethod
    def from_url(cls, url: str) -> Optional["GitUrlParts"]:
        if url.endswith(".git"):
            url = url[:-4]
        http_pattern = re.compile(r"https?://([^/]+)/([^/]+)/([^/]+)")
        ssh_pattern = re.compile(r"git@([^:]+):([^/]+)/([^/]+)")

        match = http_pattern.match(url) or ssh_pattern.match(url)
        if not match:
            return None

        hostname, owner, repo = match.groups()[0:3]
        return cls(hostname=hostname, owner=owner, repo=repo)


def _get_origin_remote(remotes: list[Remote]) -> Optional[Remote]:
    for remote in remotes:
        if remote.name == "origin":
            return remote
    return None


def git_parts_from_metadata(metadata: GitChangeMetadata) -> Optional[GitUrlParts]:
    origin_remote = _get_origin_remote(metadata.remotes)
    if origin_remote is None:
        return None
    fetch_url = origin_remote.fetch_url
    if fetch_url is None:
        return None
    git_parts = GitUrlParts.from_url(fetch_url)
    if git_parts is None:
        return None
    return git_parts


def git_url_parts_from_session(
    session: WorkspaceChangeHistory,
) -> Optional[GitUrlParts]:
    if not isinstance(session.metadata, GitChangeMetadata):
        return None
    return git_parts_from_metadata(session.metadata)


def count_session_edits(session: WorkspaceChangeHistory) -> int:
    num_edits = 0
    for file in session.files:
        num_edits += len(file.edits_history)
    return num_edits
