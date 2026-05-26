from pathlib import Path
from datetime import datetime

from pydantic import BaseModel

from edit_data.types import WorkspaceChangeHistory
from edit_data.edits import get_version_at_time

from lean_client.client import Range, Diagnostic

from lean_edits_analysis.edit_info import EditInfoCache


def get_version(
    workspace_change_history: WorkspaceChangeHistory, file: Path, edit_idx: int
) -> str:
    edit = workspace_change_history.get_dict()[file].edits_history[edit_idx]
    return get_version_at_time(
        file,
        workspace_change_history.get_dict(),
        edit.time,
    )


class DiagnosticInfo(BaseModel):
    range: Range
    severity: int
    message: str


class DiffInfo(BaseModel):
    before: str
    after: str
    # removed_ranges_before: list[Range]
    # added_ranges_after: list[Range]
    diagnostics_before: list[Diagnostic]
    diagnostics_after: list[Diagnostic]


def _get_start_time(
    workspace_change_history: WorkspaceChangeHistory, file: Path, start_edit_idx: int
) -> datetime:
    if start_edit_idx == 0:
        return datetime.min
    return (
        workspace_change_history.get_dict()[file].edits_history[start_edit_idx - 1].time
    )


def get_diff(
    workspace_change_history: WorkspaceChangeHistory,
    file: Path,
    edit_cache: EditInfoCache,
    start_edit_idx: int,  # Get the source version *prior to* this edit
    end_edit_idx: int,  # Get the target version *after* this edit
) -> DiffInfo:
    assert start_edit_idx <= end_edit_idx
    start_time = _get_start_time(workspace_change_history, file, start_edit_idx)
    before = get_version_at_time(
        file,
        workspace_change_history.get_dict(),
        start_time,
    )
    after = get_version(
        workspace_change_history,
        file,
        end_edit_idx,
    )
    prev_before, _ = edit_cache.edit_info_at_idx(start_edit_idx)
    _, after_after = edit_cache.edit_info_at_idx(end_edit_idx)
    return DiffInfo(
        before=before,
        after=after,
        diagnostics_before=prev_before.diagnostics,
        diagnostics_after=after_after.diagnostics,
    )
