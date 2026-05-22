from pydantic import BaseModel
from pathlib import Path
from datetime import datetime

from edit_data.types import WorkspaceChangeHistory
from edit_data.edits import get_version_at_edit, apply_change

from lean_edits_analysis.scratchpad import Scratchpad


class FileChangeEvent(BaseModel):
    characters_added: int
    characters_removed: int
    time: datetime


class FileChangeEvents(BaseModel):
    file: Path
    change_events: list[FileChangeEvent]

    @classmethod
    def build(
        cls,
        file: Path,
        workspace_change_history: WorkspaceChangeHistory,
        scratchpad: Scratchpad,
    ) -> "FileChangeEvents":
        file_change_history = workspace_change_history.get_dict()[file]
        change_events: list[FileChangeEvent] = []
        scratchpad.restore()
        current_file_contents = (scratchpad.repo_path / file).read_text()
        for i, edit in enumerate(file_change_history.edits_history):
            edit_characters_added = 0
            edit_characters_removed = 0
            for change in edit.changes:
                remove_contents = current_file_contents[
                    change.rangeOffset : change.rangeOffset + change.rangeLength
                ]
                add_contents = change.text
                edit_characters_added += len(add_contents)
                edit_characters_removed += len(remove_contents)
                current_file_contents = apply_change(current_file_contents, change)
            change_events.append(
                FileChangeEvent(
                    characters_added=edit_characters_added,
                    characters_removed=edit_characters_removed,
                    time=edit.time,
                )
            )
            current_file_contents = get_version_at_edit(
                file, workspace_change_history.get_dict(), i
            )[file]
        return cls(file=file, change_events=change_events)


class FileHeatmapInfo(BaseModel):
    file_data: list[FileChangeEvents]

    @classmethod
    def build(
        cls, workspace_change_history: WorkspaceChangeHistory, scratchpad: Scratchpad
    ) -> "FileHeatmapInfo":
        file_data: list[FileChangeEvents] = []
        for file_info in workspace_change_history.files:
            file = file_info.path
            change_events = FileChangeEvents.build(
                file=file,
                workspace_change_history=workspace_change_history,
                scratchpad=scratchpad,
            )
            file_data.append(change_events)
        return cls(file_data=file_data)
