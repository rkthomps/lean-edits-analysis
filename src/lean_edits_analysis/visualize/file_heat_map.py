from pydantic import BaseModel
from pathlib import Path
from datetime import datetime

from edit_data.types import WorkspaceChangeHistory
from edit_data.edits import apply_change, get_version_at_time


class FileChangeEvent(BaseModel):
    characters_added: int
    characters_removed: int
    time: datetime
    edit_index: int


class FileChangeEvents(BaseModel):
    file: Path
    change_events: list[FileChangeEvent]

    @classmethod
    def build(
        cls,
        file: Path,
        workspace_change_history: WorkspaceChangeHistory,
    ) -> "FileChangeEvents":
        file_change_history = workspace_change_history.get_dict()[file]
        change_events: list[FileChangeEvent] = []
        current_file_contents = get_version_at_time(
            file, workspace_change_history.get_dict(), datetime.min
        )
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
                    edit_index=i,
                )
            )
            current_file_contents = get_version_at_time(
                file, workspace_change_history.get_dict(), edit.time
            )
        return cls(file=file, change_events=change_events)


class FileHeatmapInfo(BaseModel):
    file_data: list[FileChangeEvents]

    @classmethod
    def build(
        cls, workspace_change_history: WorkspaceChangeHistory
    ) -> "FileHeatmapInfo":
        file_data: list[FileChangeEvents] = []
        for file_info in workspace_change_history.files:
            file = file_info.path
            change_events = FileChangeEvents.build(
                file=file,
                workspace_change_history=workspace_change_history,
            )
            file_data.append(change_events)
        return cls(file_data=file_data)
