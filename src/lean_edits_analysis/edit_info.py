import logging
import shutil
import click
from filelock import FileLock
from typing import Iterable, Optional
from pydantic import BaseModel
from pathlib import Path
from dataclasses import dataclass

from lean_edits_analysis.scratchpad import Scratchpad, ScratchpadError
from lean_edits_analysis.data import (
    load_matching_sessions,
    find_repo_metadata,
    repo_metadata_iter,
)
from lean_edits_analysis.util import (
    GitUrlParts,
    git_parts_from_metadata,
    count_session_edits,
)

from edit_data.types import Edit, WorkspaceChangeHistory, GitChangeMetadata
from edit_data.edits import get_version_at_edit

from lean_client.client import (
    Diagnostic,
    Decl,
    LeanClient,
    FindDeclsRequest,
    FindDeclsResponse,
)

logger = logging.getLogger(__name__)

CACHE_LOC = Path("cache")
LOCKS_LOC = Path("locks")


class EditInfo(BaseModel):
    diagnostics: list[Diagnostic]
    decls: list[Decl]


def _get_changed_files(
    previous_version: Optional[dict[Path, str]], current_version: dict[Path, str]
) -> set[Path]:
    if previous_version is None:
        return set(current_version.keys())
    changed_files = set()
    for file in current_version.keys():
        if (
            file not in previous_version
            or previous_version[file] != current_version[file]
        ):
            changed_files.add(file)
    return changed_files


def _gather_edit_info(client: LeanClient, file_uri: str, timeout: int) -> EditInfo:
    decls = client.send_request(FindDeclsRequest(uri=file_uri), timeout=timeout)
    assert isinstance(decls, FindDeclsResponse)
    diagnostics = client.wait_for_diagnostics(file_uri, timeout=timeout)
    edit_info = EditInfo(diagnostics=diagnostics.diagnostics, decls=decls.decls)
    return edit_info


def iter_edits_with_info(
    scratchpad: Scratchpad,
    session: WorkspaceChangeHistory,
    file: Path,
    edit_start_idx: int = 0,
    client_timeout: int = 240,
) -> Iterable[tuple[int, EditInfo, Edit, EditInfo]]:
    """ """
    full_file_path = scratchpad.repo_path / file
    file_uri = full_file_path.resolve().as_uri()
    file_history = session.get_dict()[file]
    previous_version: Optional[dict[Path, str]] = None
    client = LeanClient.start(
        scratchpad.repo_path, instrument_server=True, timeout=client_timeout
    )

    # Initialize previous version
    if edit_start_idx == 0:
        scratchpad.restore()
        client.open_file(file_uri, full_file_path.read_text())
        prev_edit_info = _gather_edit_info(client, file_uri, client_timeout)
    else:
        prev_version = get_version_at_edit(file, session.get_dict(), edit_start_idx - 1)
        scratchpad.write_version(prev_version)
        client.open_file(file_uri, prev_version[file])
        prev_edit_info = _gather_edit_info(client, file_uri, client_timeout)

    try:
        for edit_idx in range(edit_start_idx, len(file_history.edits_history)):
            edit = file_history.edits_history[edit_idx]
            current_version = get_version_at_edit(file, session.get_dict(), edit_idx)
            scratchpad.write_version(current_version)
            changed_files = _get_changed_files(previous_version, current_version)
            previous_version = current_version
            if len(changed_files) > 1:
                client = client.restart()
                client.open_file(file_uri, full_file_path.read_text())
            else:
                client.change_file(file_uri, full_file_path.read_text())

            decls = client.send_request(
                FindDeclsRequest(uri=file_uri), timeout=client_timeout
            )
            assert isinstance(decls, FindDeclsResponse)
            diagnostics = client.wait_for_diagnostics(file_uri, timeout=client_timeout)
            edit_info = EditInfo(diagnostics=diagnostics.diagnostics, decls=decls.decls)
            yield edit_idx, prev_edit_info, edit, edit_info
            prev_edit_info = edit_info

    finally:
        client.shutdown()


class EditInfoCache(BaseModel):
    scratchpad_repo_owner: str
    scratchpad_repo_name: str
    scratchpad_commit_sha: str
    file: Path

    @property
    def cache_loc(self) -> Path:
        return (
            CACHE_LOC
            / self.scratchpad_repo_owner
            / self.scratchpad_repo_name
            / self.scratchpad_commit_sha
            / self.file
        )

    @property
    def prev_edit_info_loc(self) -> Path:
        return self.cache_loc / "prev_edit_info.json"

    @property
    def edit_infos_loc(self) -> Path:
        return self.cache_loc / "edit_infos.jsonl"

    def edit_info_at_idx(self, idx: int) -> tuple[EditInfo, EditInfo]:
        if not self.exists_and_has_correct_num_edits(None, self.file):
            raise ValueError(
                f"Cache does not exist for file {self.file} at {self.cache_loc}"
            )
        if idx < 0:
            raise ValueError(f"Edit index {idx} must be non-negative")
        if idx == 0:
            prev_edit_info = EditInfo.model_validate_json(
                self.prev_edit_info_loc.read_text()
            )
        else:
            prev_edit_info = None

        with self.edit_infos_loc.open() as edit_infos_file:
            for i, line in enumerate(edit_infos_file):
                if i == idx - 1:
                    prev_edit_info = EditInfo.model_validate_json(line)
                elif i == idx:
                    assert (
                        prev_edit_info is not None
                    ), f"Previous edit info not found for edit index {idx}"
                    edit_info = EditInfo.model_validate_json(line)
                    return prev_edit_info, edit_info
                elif i < idx:
                    continue
                else:
                    assert False
        raise ValueError(f"Edit index {idx} out of range for cache at {self.cache_loc}")

    def iter_edits_with_info(
        self, session: WorkspaceChangeHistory, file: Path, edit_start_idx: int = 0
    ) -> Iterable[tuple[int, EditInfo, Edit, EditInfo]]:
        if edit_start_idx == 0:
            assert (
                self.prev_edit_info_loc.exists()
            ), f"Prev edit info not found at {self.prev_edit_info_loc}"
            prev_edit_info = EditInfo.model_validate_json(
                self.prev_edit_info_loc.read_text()
            )

        with self.edit_infos_loc.open() as f:
            for i, line in enumerate(f):
                if i == (edit_start_idx - 1):
                    prev_edit_info = EditInfo.model_validate_json(line)
                elif i < edit_start_idx:
                    continue
                else:
                    assert i >= edit_start_idx
                    assert prev_edit_info is not None
                    edit_info = EditInfo.model_validate_json(line)
                    edit = session.get_dict()[file].edits_history[i]
                    yield i, prev_edit_info, edit, edit_info
                    prev_edit_info = edit_info

    def exists_and_has_correct_num_edits(
        self, session: WorkspaceChangeHistory, file: Path
    ) -> bool:
        if not isinstance(session.metadata, GitChangeMetadata):
            raise ValueError(
                f"Session metadata is not GitChangeMetadata. Found {type(session.metadata)}"
            )
        if not self.cache_loc.exists():
            return False
        if not self.prev_edit_info_loc.exists() or not self.edit_infos_loc.exists():
            return False
        with self.edit_infos_loc.open() as f:
            num_cached_edits = sum(1 for _ in f)
        num_session_edits = len(session.get_dict()[file].edits_history)
        if num_cached_edits != num_session_edits:
            logger.warning(
                f"Cache for {file} has {num_cached_edits} edits, but session has {num_session_edits} edits"
            )
            return False
        return True

    def delete_cache(self):
        if self.cache_loc.exists():
            shutil.rmtree(self.cache_loc)

    @classmethod
    def get_cache(cls, scratchpad: Scratchpad, file: Path) -> "EditInfoCache":
        cache = cls(
            scratchpad_repo_owner=scratchpad.repo_owner,
            scratchpad_repo_name=scratchpad.repo_name,
            scratchpad_commit_sha=scratchpad.commit_sha,
            file=file,
        )
        return cache

    @property
    def num_edits(self) -> int:
        if not self.cache_loc.exists():
            return 0
        if not self.prev_edit_info_loc.exists():
            return 0
        if not self.edit_infos_loc.exists():
            return 0
        with self.edit_infos_loc.open() as f:
            num_cached_edits = sum(1 for _ in f)
        return num_cached_edits

    def create(self, scratchpad: Scratchpad, session: WorkspaceChangeHistory) -> None:
        existing_num_edits = self.num_edits
        self.cache_loc.mkdir(parents=True, exist_ok=True)
        logger.info(
            f"Found {existing_num_edits} cached edits for file {self.file}. Creating cache starting from edit {existing_num_edits}"
        )
        with (
            self.prev_edit_info_loc.open("a") as prev_edit_info_file,
            self.edit_infos_loc.open("a") as edit_infos_file,
        ):
            for edit_idx, prev_edit_info, _, edit_info in iter_edits_with_info(
                scratchpad, session, self.file, edit_start_idx=existing_num_edits
            ):
                if edit_idx % 25 == 0:
                    logger.info(
                        f"Creating cache for edit {edit_idx} of file {self.file}"
                    )
                if edit_idx == 0:
                    prev_edit_info_file.write(prev_edit_info.model_dump_json())
                edit_infos_file.write(edit_info.model_dump_json() + "\n")


@click.group()
def cli():
    pass


def _cache_session_file(
    scratchpad: Scratchpad, session: WorkspaceChangeHistory, file: Path
) -> None:
    cache = EditInfoCache.get_cache(scratchpad, file)
    cache.create(scratchpad, session)


def get_repo_lock(repo_owner: str, repo_name: str) -> FileLock:
    repo_lock_path = LOCKS_LOC / repo_owner / repo_name / "repo.lock"
    repo_lock_path.parent.mkdir(parents=True, exist_ok=True)
    return FileLock(repo_lock_path)


def need_to_cache(
    repo_owner: str, repo_name: str, commit_sha: str, session: WorkspaceChangeHistory
) -> bool:
    for file in session.files:
        cache = EditInfoCache(
            scratchpad_repo_owner=repo_owner,
            scratchpad_repo_name=repo_name,
            scratchpad_commit_sha=commit_sha,
            file=file.path,
        )
        if not cache.exists_and_has_correct_num_edits(session, file.path):
            return True
    return False


def _cache_session(
    repo_owner: str, repo_name: str, commit_sha: str, session: WorkspaceChangeHistory
):
    scratchpad = Scratchpad(
        repo_owner=repo_owner, repo_name=repo_name, commit_sha=commit_sha
    )
    with get_repo_lock(repo_owner, repo_name):
        scratchpad.setup()
        for file in session.files:
            _cache_session_file(scratchpad, session, file.path)


def cache_repo_iter(
    repo_owner: str, repo_name: str
) -> Iterable[tuple[WorkspaceChangeHistory, bool]]:
    for session in load_matching_sessions(repo_owner, repo_name):
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
        num_files = len(session.files)
        num_edits = count_session_edits(session)
        logger.info(
            f"Processing session for {git_parts.owner}/{git_parts.repo} at commit {session.metadata.head} with {num_files} files and {num_edits} edits"
        )
        try:
            if not need_to_cache(
                repo_owner=git_parts.owner,
                repo_name=git_parts.repo,
                commit_sha=session.metadata.head,
                session=session,
            ):
                logger.info(
                    f"Cache already exists for {git_parts.owner}/{git_parts.repo} at commit {session.metadata.head}. Skipping caching."
                )
                yield session, True
                continue
            logger.info(
                f"Caching session for {git_parts.owner}/{git_parts.repo} at commit {session.metadata.head}"
            )
            _cache_session(
                git_parts.owner, git_parts.repo, session.metadata.head, session
            )
            yield session, True
        except ScratchpadError as e:
            logger.error(
                f"Failed to cache session for {git_parts.owner}/{git_parts.repo} at commit {session.metadata.head} due to scratchpad error: {e}"
            )
            yield session, False

        except Exception as e:
            logger.exception(
                f"Failed to cache session for {git_parts.owner}/{git_parts.repo} at commit {session.metadata.head}. Error: {e}"
            )
            yield session, False


def _cache_repo(repo_owner: str, repo_name: str):
    for _, success in cache_repo_iter(repo_owner, repo_name):
        logger.info(
            f"Finished caching session for {repo_owner}/{repo_name} with success={success}"
        )


@dataclass
class _CompleteFile:
    path: Path
    num_edits: int


@dataclass
class _IncompleteFile:
    path: Path
    num_edits: int
    num_cached_edits: int


@dataclass
class _SessionProgress:
    owner: str
    repo: str
    commit_sha: str
    incomplete_files: list[_IncompleteFile]
    complete_files: list[_CompleteFile]

    @property
    def done(self) -> bool:
        return len(self.incomplete_files) == 0

    @property
    def completed_edits(self) -> int:
        return sum(file.num_edits for file in self.complete_files)

    @property
    def num_cached_edits(self) -> int:
        return (
            sum(file.num_cached_edits for file in self.incomplete_files)
            + self.completed_edits
        )

    @property
    def num_edits(self) -> int:
        return self.completed_edits + sum(
            file.num_edits for file in self.incomplete_files
        )


@cli.command()
def progress():
    for repo_metadata, session in repo_metadata_iter():
        assert isinstance(session.metadata, GitChangeMetadata)
        incomplete_files: list[_IncompleteFile] = []
        complete_files: list[_CompleteFile] = []
        for file in session.files:
            cache = EditInfoCache(
                scratchpad_repo_owner=repo_metadata.repo_owner,
                scratchpad_repo_name=repo_metadata.repo_name,
                scratchpad_commit_sha=repo_metadata.sessions[0].head,
                file=file.path,
            )
            num_cached_edits = cache.num_edits
            num_session_edits = len(session.get_dict()[file.path].edits_history)
            if num_cached_edits == num_session_edits:
                complete_files.append(
                    _CompleteFile(path=file.path, num_edits=num_session_edits)
                )
            else:
                assert num_cached_edits < num_session_edits
                incomplete_files.append(
                    _IncompleteFile(
                        path=file.path,
                        num_edits=num_session_edits,
                        num_cached_edits=num_cached_edits,
                    )
                )
        assert len(incomplete_files) + len(complete_files) == len(session.files)
        progress = _SessionProgress(
            owner=repo_metadata.repo_owner,
            repo=repo_metadata.repo_name,
            commit_sha=repo_metadata.sessions[0].head,
            incomplete_files=incomplete_files,
            complete_files=complete_files,
        )
        if progress.done:
            # with checkmark emoji
            print(
                f"{progress.owner}/{progress.repo} at commit {progress.commit_sha} ✅ ({progress.completed_edits} edits)"
            )
        elif progress.num_cached_edits == 0:
            print(
                f"{progress.owner}/{progress.repo} at commit {progress.commit_sha} ❌. Processing not started for {len(incomplete_files)} files with {progress.num_edits} cached edits."
            )
        else:
            print(
                f"Progress for {progress.owner}/{progress.repo} at commit {progress.commit_sha}:"
            )
            for file in progress.complete_files:
                print(
                    f"  {file.path}: {file.num_edits} edits ✅ (cached {file.num_edits} edits)"
                )
            for file in progress.incomplete_files:
                print(
                    f"  {file.path}: {file.num_edits} edits ⏳ (cached ({file.num_cached_edits} / {file.num_edits}) edits)"
                )


@cli.command()
@click.argument("repo_owner")
@click.argument("repo_name")
def repo(repo_owner: str, repo_name: str):
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    logging.getLogger("lean_edits_analysis").setLevel(logging.INFO)
    logging.getLogger(__name__).setLevel(logging.INFO)
    _cache_repo(repo_owner, repo_name)


# Parcly-Taxel
# TonelliShanks


@cli.command()
@click.option("--workers", default=1, help="Number of worker processes to use")
def everything(workers: int):
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    logging.getLogger("lean_edits_analysis").setLevel(logging.INFO)
    logging.getLogger(__name__).setLevel(logging.INFO)
    repo_metadata = find_repo_metadata()
    logger.info(f"Found metadata for {len(repo_metadata)} repos")
    total_sessions = sum(repo.total_sessions for repo in repo_metadata)
    total_edits = sum(repo.total_edits for repo in repo_metadata)
    logger.info(f"Total sessions: {total_sessions}")
    logger.info(f"Total edits: {total_edits}")
    for repo in repo_metadata:
        logger.info(
            f"Repo {repo.repo_owner}/{repo.repo_name} has {len(repo.sessions)} sessions and {repo.total_edits} edits"
        )

    # for repo in repo_metadata:
    #     logger.info(
    #         f"Processing repo {repo.repo_owner}/{repo.repo_name} with {len(repo.sessions)} sessions and {_total_num_edits(repo)} edits"
    #     )
    #     _cache_repo(repo.repo_owner, repo.repo_name)


if __name__ == "__main__":
    cli()
