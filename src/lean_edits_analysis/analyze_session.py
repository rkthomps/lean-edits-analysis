import logging
from typing import Iterable, Optional
from pathlib import Path
from dataclasses import dataclass

from edit_data.types import (
    Edit,
    Range as EditRange,
    WorkspaceChangeHistory,
)
from edit_data.zip_edits import load_workspace_history
from edit_data.edits import get_version_at_edit


from lean_edits_analysis.common import DATA_LOC
from lean_edits_analysis.scratchpad import Scratchpad

from lean_client.client import (
    FindTheoremsRequest,
    FindTheoremsResponse,
    FindDeclsRequest,
    FindDeclsResponse,
    Decl,
    LeanClient,
    Range,
    Position,
)

logger = logging.getLogger(__name__)


@dataclass
class ChangedDeclarations:
    decls_added: set[str]
    decls_removed: set[str]
    decls_modified: set[str]


# def get_changed_declarations(
#     workspace_change_history: WorkspaceChangeHistory,
#     file: Path,
# ) -> Iterable[tuple[str, ]]
#     pass


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


def analyze_session(workspace_change_history: WorkspaceChangeHistory):
    pass


def load_last_commit_history(commit_data_path: Path) -> WorkspaceChangeHistory:
    commit_uploads = list(commit_data_path.iterdir())
    if len(commit_uploads) == 0:
        raise ValueError(f"No uploads found for commit data path: {commit_data_path}")
    latest_upload = max(commit_uploads, key=lambda p: int(p.stem))
    return load_workspace_history(latest_upload)


def load_session(
    repo_owner: str, repo_name: str, commit_sha: str
) -> WorkspaceChangeHistory:
    for workspace_data in DATA_LOC.iterdir():
        if repo_owner not in workspace_data.name:
            continue
        if repo_name not in workspace_data.name:
            continue
        for commit_data in workspace_data.iterdir():
            if commit_sha == commit_data.name:
                return load_last_commit_history(commit_data)
    raise ValueError(
        f"Could not find session for repo {repo_owner}/{repo_name} at commit {commit_sha}"
    )


def get_decls(
    client: LeanClient, scratchpad: Scratchpad, file_relpath: Path
) -> list[Decl]:
    file_path = (scratchpad.repo_path / file_relpath).resolve()
    file_uri = file_path.as_uri()
    response = client.send_request(FindDeclsRequest(uri=file_uri))
    assert isinstance(
        response, FindDeclsResponse
    ), f"Expected FindDeclsResponse, got {type(response)}"
    return response.decls


def get_added_decls(decls_before: list[Decl], decls_after: list[Decl]) -> list[Decl]:
    named_decls_before = [d for d in decls_before if d.name is not None]
    named_decls_after = [d for d in decls_after if d.name is not None]
    decls_before_dict = {d.name: d for d in named_decls_before}
    decls_after_dict = {d.name: d for d in named_decls_after}
    added_decl_names = set(decls_after_dict.keys()) - set(decls_before_dict.keys())
    return [decls_after_dict[name] for name in added_decl_names]


def get_removed_decls(decls_before: list[Decl], decls_after: list[Decl]) -> list[Decl]:
    named_decls_before = [d for d in decls_before if d.name is not None]
    named_decls_after = [d for d in decls_after if d.name is not None]
    decls_before_dict = {d.name: d for d in named_decls_before}
    decls_after_dict = {d.name: d for d in named_decls_after}
    removed_decl_names = set(decls_before_dict.keys()) - set(decls_after_dict.keys())
    return [decls_before_dict[name] for name in removed_decl_names]


def get_modified_decls(decls_before: list[Decl], decls_after: list[Decl]) -> list[Decl]:
    named_decls_before = [d for d in decls_before if d.name is not None]
    named_decls_after = [d for d in decls_after if d.name is not None]
    decls_before_dict = {d.name: d for d in named_decls_before}
    decls_after_dict = {d.name: d for d in named_decls_after}
    common_decl_names = set(decls_before_dict.keys()) & set(decls_after_dict.keys())
    modified_decl_names = {
        name
        for name in common_decl_names
        if decls_before_dict[name].content != decls_after_dict[name].content
    }
    return [decls_after_dict[name] for name in modified_decl_names]


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


def to_client_range(range: EditRange) -> Range:
    return Range(
        start=Position(line=range.start.line, character=range.start.character),
        end=Position(line=range.end.line, character=range.end.character),
    )


def find_edit_decls(decls: list[Decl], edit: Edit) -> list[Decl]:
    """
    Find the decls that overlap with the given edit.
    """
    overlapping_decls: list[Decl] = []
    for decl in decls:
        for change in edit.changes:
            if decl.range.intersect(to_client_range(change.range)):
                overlapping_decls.append(decl)
                break
    return overlapping_decls


def replay_edits_single_file(
    scratchpad: Scratchpad, session: WorkspaceChangeHistory, file: Path
) -> dict[str, list[Edit]]:
    """
    Beginning assumption:
    - other files don't change.
    - when other files change, we need to restart the language server
    - TODO: write a check for other files changing.
    """
    full_file_path = scratchpad.repo_path / file
    file_uri = full_file_path.resolve().as_uri()
    file_history = session.get_dict()[file]
    previous_version: Optional[dict[Path, str]] = None
    client = LeanClient.start(scratchpad.repo_path, instrument_server=True)
    client.open_file(file_uri, full_file_path.read_text())
    decl_edits: dict[str, list[Edit]] = {}
    try:
        for i, edit in enumerate(file_history.edits_history):
            logger.info(
                f"Replaying edit {i}/{len(file_history.edits_history)} for file {file}"
            )
            if i % 50 == 0:
                edit_lengths = {n: len(edits) for n, edits in decl_edits.items()}
                logger.info(f"Current decl edit counts: {edit_lengths}")
            current_version = get_version_at_edit(file, session.get_dict(), i)
            scratchpad.write_version(current_version)
            changed_files = _get_changed_files(previous_version, current_version)
            previous_version = current_version
            if len(changed_files) < 1:
                logger.info(f"No changes detected at edit {i} for file {file}")
                continue
            elif len(changed_files) > 1:
                # TODO: re-open files on restart
                client = client.restart()
                client.open_file(file_uri, full_file_path.read_text())
            else:
                client.change_file(file_uri, full_file_path.read_text())

            decls = get_decls(client, scratchpad, file)
            edit_decls = find_edit_decls(decls, edit)
            for decl in edit_decls:
                if decl.name is None:
                    continue
                if decl.name not in decl_edits:
                    decl_edits[decl.name] = []
                decl_edits[decl.name].append(edit)
        return decl_edits
    finally:
        client.shutdown()


def show_decl(decl: Decl) -> str:
    return f"{decl.name} ({decl.info.kind})"


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
    # scratchpad.setup()
    changed_files = get_changed_files(session_change_history)

    for file, num_edits in changed_files:
        logger.info(f"Getting decls for changed file {file}")

        full_file_path = scratchpad.repo_path / file
        file_uri = full_file_path.resolve().as_uri()
        before = get_version_at_edit(file, session_change_history.get_dict(), 0)
        scratchpad.write_version(before)
        with LeanClient.start(
            scratchpad.repo_path, instrument_server=True, timeout=30
        ) as client:
            client.open_file(file_uri, full_file_path.read_text())
            decls_before = get_decls(client, scratchpad, file)
            logger.info(f"Decls before: {len(decls_before)} decls")

        after = get_version_at_edit(
            file, session_change_history.get_dict(), num_edits - 1
        )
        scratchpad.write_version(after)
        with LeanClient.start(
            scratchpad.repo_path, instrument_server=True, timeout=30
        ) as client:
            client.open_file(file_uri, full_file_path.read_text())
            decls_after = get_decls(client, scratchpad, file)
            logger.info(f"Decls after: {len(decls_after)} decls")

        added_decls = get_added_decls(decls_before, decls_after)
        removed_decls = get_removed_decls(decls_before, decls_after)
        modified_decls = get_modified_decls(decls_before, decls_after)

        print(f"Added decls in {file}:")
        for decl in added_decls:
            print(f"  {show_decl(decl)}")
        print(f"Removed decls in {file}:")
        for decl in removed_decls:
            print(f"  {show_decl(decl)}")
        print(f"Modified decls in {file}:")
        for decl in modified_decls:
            print(f"  {show_decl(decl)}")

        edits_per_decl = replay_edits_single_file(
            scratchpad, session_change_history, file
        )
        for decl_name, edits in edits_per_decl.items():
            print(f"- Decl {decl_name} has {len(edits)} edits.")


if __name__ == "__main__":
    debug_session()
