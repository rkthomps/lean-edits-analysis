from pathlib import Path
from pydantic import BaseModel
from datetime import datetime

from edit_data.types import WorkspaceChangeHistory, ContentChange, GitChangeMetadata
from edit_data.edits import apply_change, get_version_at_time

from lean_edits_analysis.edit_info import EditInfoCache
from lean_edits_analysis.util import GitUrlParts, to_client_range

from lean_client.client import Decl


class DeclChangeEvent(BaseModel):
    characters_added: int
    characters_removed: int
    time: datetime
    edit_index: int


class DeclChangeEvents(BaseModel):
    decl: Decl
    change_events: list[DeclChangeEvent]


def _get_overlapping_decls(decls: list[Decl], change: ContentChange) -> list[Decl]:
    overlapping_decls: list[Decl] = []
    for decl in decls:
        if decl.range.intersect(to_client_range(change.range)):
            overlapping_decls.append(decl)
    return overlapping_decls


class FileDeclChangeEvents(BaseModel):
    file: Path
    decl_changes: list[DeclChangeEvents]

    @classmethod
    def build(
        cls,
        file: Path,
        workspace_change_history: WorkspaceChangeHistory,
        cache: EditInfoCache,
    ) -> "FileDeclChangeEvents":
        decl_changes: dict[str, tuple[Decl, list[DeclChangeEvent]]] = {}
        current_file_contents = get_version_at_time(
            file, workspace_change_history.get_dict(), datetime.min
        )
        for edit_idx, prev_info, edit, _ in cache.iter_edits_with_info(
            workspace_change_history, file, edit_start_idx=0
        ):
            for decl in prev_info.decls:
                if decl.name is None:
                    continue
                if decl.name not in decl_changes:
                    decl_changes[decl.name] = (decl, [])
            edit_characters_added = 0
            edit_characters_removed = 0
            edit_decls: dict[str, Decl] = {}
            for change in edit.changes:
                remove_contents = current_file_contents[
                    change.rangeOffset : change.rangeOffset + change.rangeLength
                ]
                add_contents = change.text
                edit_characters_added += len(add_contents)
                edit_characters_removed += len(remove_contents)
                current_file_contents = apply_change(current_file_contents, change)
                overlapping_decls = _get_overlapping_decls(prev_info.decls, change)
                for decl in overlapping_decls:
                    if decl.name is None:
                        continue
                    edit_decls[decl.name] = decl
            for decl_name, decl in edit_decls.items():
                assert (
                    decl_name in decl_changes
                ), f"Decl {decl_name} not found in decl_changes"
                decl_changes[decl_name][1].append(
                    DeclChangeEvent(
                        characters_added=edit_characters_added,
                        characters_removed=edit_characters_removed,
                        time=edit.time,
                        edit_index=edit_idx,
                    )
                )
            current_file_contents = get_version_at_time(
                file, workspace_change_history.get_dict(), edit.time
            )

        decl_change_list: list[DeclChangeEvents] = []
        for decl_name, (decl, change_events) in decl_changes.items():
            decl_change_list.append(
                DeclChangeEvents(
                    decl=decl,
                    change_events=change_events,
                )
            )

        decl_change_list.sort(key=lambda d: d.decl.range.start.line)
        return cls(file=file, decl_changes=decl_change_list)


class DeclHeatmapInfo(BaseModel):
    file_data: list[FileDeclChangeEvents]

    @classmethod
    def build(
        cls, workspace_change_history: WorkspaceChangeHistory, git_parts: GitUrlParts
    ) -> "DeclHeatmapInfo":
        file_data: list[FileDeclChangeEvents] = []
        assert isinstance(workspace_change_history.metadata, GitChangeMetadata)
        for file_info in workspace_change_history.files:
            file = file_info.path
            cache = EditInfoCache(
                scratchpad_repo_owner=git_parts.owner,
                scratchpad_repo_name=git_parts.repo,
                scratchpad_commit_sha=workspace_change_history.metadata.head,
                file=file,
            )
            assert cache.exists_and_has_correct_num_edits(
                workspace_change_history, file
            )
            change_events = FileDeclChangeEvents.build(
                file=file,
                workspace_change_history=workspace_change_history,
                cache=cache,
            )
            file_data.append(change_events)

        file_data.sort(key=lambda f: f.file)
        return cls(file_data=file_data)
