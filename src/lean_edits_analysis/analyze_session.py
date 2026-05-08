from typing import Iterable
from pathlib import Path
from dataclasses import dataclass

from edit_data.types import (
    WorkspaceChangeHistory,
)
from edit_data.zip_edits import load_workspace_history

from lean_edits_analysis.common import DATA_LOC
from lean_edits_analysis.scratchpad import Scratchpad


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


if __name__ == "__main__":
    session = load_session(
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
