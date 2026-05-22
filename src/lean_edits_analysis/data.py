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
from lean_edits_analysis.scratchpad import Scratchpad
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


def debug_session():

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    logging.getLogger("lean_edits_analysis").setLevel(logging.INFO)
    logging.getLogger("__name__").setLevel(logging.INFO)

    session_change_history = load_session(
        repo_owner="rkthomps",
        repo_name="lean-time-m",
        commit_sha="880d1ca2ed73bb4427396fd635e301934142a97c",
    )

    scratchpad = Scratchpad(
        repo_owner="rkthomps",
        repo_name="lean-time-m",
        commit_sha="880d1ca2ed73bb4427396fd635e301934142a97c",
    )
    scratchpad.setup()
    changed_files = get_changed_files(session_change_history)
    for file, _ in changed_files:
        cache = EditInfoCache.get_cache(scratchpad, file)
        if not cache.exists_and_has_correct_num_edits(
            session_change_history, file, scratchpad
        ):
            cache.delete_cache()
            logger.info(f"Creating cache for file {file}")
            cache.create(scratchpad, session=session_change_history)

    # for file, num_edits in changed_files:
    #     logger.info(f"Getting decls for changed file {file}")

    #     full_file_path = scratchpad.repo_path / file
    #     file_uri = full_file_path.resolve().as_uri()
    #     before = get_version_at_edit(file, session_change_history.get_dict(), 0)
    #     scratchpad.write_version(before)
    #     with LeanClient.start(
    #         scratchpad.repo_path, instrument_server=True, timeout=30
    #     ) as client:
    #         client.open_file(file_uri, full_file_path.read_text())
    #         decls_before = get_decls(client, scratchpad, file)
    #         logger.info(f"Decls before: {len(decls_before)} decls")

    #     after = get_version_at_edit(
    #         file, session_change_history.get_dict(), num_edits - 1
    #     )
    #     scratchpad.write_version(after)
    #     with LeanClient.start(
    #         scratchpad.repo_path, instrument_server=True, timeout=30
    #     ) as client:
    #         client.open_file(file_uri, full_file_path.read_text())
    #         decls_after = get_decls(client, scratchpad, file)
    #         logger.info(f"Decls after: {len(decls_after)} decls")

    #     added_decls = get_added_decls(decls_before, decls_after)
    #     removed_decls = get_removed_decls(decls_before, decls_after)
    #     modified_decls = get_modified_decls(decls_before, decls_after)

    #     print(f"Added decls in {file}:")
    #     for decl in added_decls:
    #         print(f"  {show_decl(decl)}")
    #     print(f"Removed decls in {file}:")
    #     for decl in removed_decls:
    #         print(f"  {show_decl(decl)}")
    #     print(f"Modified decls in {file}:")
    #     for decl in modified_decls:
    #         print(f"  {show_decl(decl)}")

    #     edits_per_decl = replay_edits_single_file(
    #         scratchpad, session_change_history, file
    #     )
    #     for decl_name, edits in edits_per_decl.items():
    #         print(f"- Decl {decl_name} has {len(edits)} edits.")


if __name__ == "__main__":
    debug_session()
