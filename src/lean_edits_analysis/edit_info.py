import logging
import shutil
from typing import Iterable, Optional
from pydantic import BaseModel
from pathlib import Path

from lean_edits_analysis.scratchpad import Scratchpad

from edit_data.types import Edit, WorkspaceChangeHistory
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


def _gather_edit_info(client: LeanClient, file_uri: str) -> EditInfo:
    decls = client.send_request(FindDeclsRequest(uri=file_uri))
    assert isinstance(decls, FindDeclsResponse)
    diagnostics = client.wait_for_diagnostics(file_uri)
    edit_info = EditInfo(diagnostics=diagnostics.diagnostics, decls=decls.decls)
    return edit_info


def iter_edits_with_info(
    scratchpad: Scratchpad,
    session: WorkspaceChangeHistory,
    file: Path,
    edit_start_idx: int = 0,
) -> Iterable[tuple[int, EditInfo, Edit, EditInfo]]:
    """ """
    full_file_path = scratchpad.repo_path / file
    file_uri = full_file_path.resolve().as_uri()
    file_history = session.get_dict()[file]
    previous_version: Optional[dict[Path, str]] = None
    client = LeanClient.start(scratchpad.repo_path, instrument_server=True, timeout=5)

    # Initialize previous version
    if edit_start_idx == 0:
        scratchpad.restore()
        client.open_file(file_uri, full_file_path.read_text())
        prev_edit_info = _gather_edit_info(client, file_uri)
    else:
        prev_version = get_version_at_edit(file, session.get_dict(), edit_start_idx - 1)
        scratchpad.write_version(prev_version)
        client.open_file(file_uri, prev_version[file])
        prev_edit_info = _gather_edit_info(client, file_uri)

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

            decls = client.send_request(FindDeclsRequest(uri=file_uri))
            assert isinstance(decls, FindDeclsResponse)
            diagnostics = client.wait_for_diagnostics(file_uri)
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
        else:
            with self.edit_infos_loc.open() as f:
                for i, line in enumerate(f):
                    if i < edit_start_idx:
                        continue
                    if i == (edit_start_idx - 1):
                        prev_edit_info = EditInfo.model_validate_json(line)
                    else:
                        assert i >= edit_start_idx
                        assert prev_edit_info is not None
                        edit_info = EditInfo.model_validate_json(line)
                        edit = session.get_dict()[file].edits_history[i]
                        yield i, prev_edit_info, edit, edit_info
                        prev_edit_info = edit_info

    def exists_and_has_correct_num_edits(
        self, session: WorkspaceChangeHistory, file: Path, scratchpad: Scratchpad
    ) -> bool:
        if not self.cache_loc.exists():
            return False
        if not self.prev_edit_info_loc.exists() or not self.edit_infos_loc.exists():
            return False
        if self.scratchpad_repo_owner != scratchpad.repo_owner:
            return False
        if self.scratchpad_repo_name != scratchpad.repo_name:
            return False
        if self.scratchpad_commit_sha != scratchpad.commit_sha:
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

    def create(self, scratchpad: Scratchpad, session: WorkspaceChangeHistory) -> None:
        self.cache_loc.mkdir(parents=True)
        with (
            self.prev_edit_info_loc.open("w") as prev_edit_info_file,
            self.edit_infos_loc.open("w") as edit_infos_file,
        ):
            for edit_idx, prev_edit_info, edit, edit_info in iter_edits_with_info(
                scratchpad, session, self.file
            ):
                if edit_idx % 25 == 0:
                    logger.info(
                        f"Creating cache for edit {edit_idx} of file {self.file}"
                    )
                if edit_idx == 0:
                    prev_edit_info_file.write(prev_edit_info.model_dump_json())
                edit_infos_file.write(edit_info.model_dump_json() + "\n")
