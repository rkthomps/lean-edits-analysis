import logging
import click
from pathlib import Path

from edit_data.types import WorkspaceChangeHistory

from lean_edits_analysis.analyze_session import load_session
from lean_edits_analysis.scratchpad import Scratchpad
from lean_edits_analysis.edit_info import EditInfoCache

from lean_edits_analysis.visualize.build import write_session_data
from lean_edits_analysis.visualize.file_heat_map import FileHeatmapInfo
from lean_edits_analysis.visualize.decl_heat_map import DeclHeatmapInfo


def file_heatmap_data(
    workspace_change_history: WorkspaceChangeHistory,
    scratchpad: Scratchpad,
    output_path: Path,
) -> FileHeatmapInfo:
    change_events = FileHeatmapInfo.build(workspace_change_history, scratchpad)
    with open(output_path, "w") as fout:
        fout.write(change_events.model_dump_json())
    return change_events


def decl_heatmap_data(
    workspace_change_history: WorkspaceChangeHistory,
    scratchpad: Scratchpad,
    output_path: Path,
):
    change_events = DeclHeatmapInfo.build(workspace_change_history, scratchpad)
    with open(output_path, "w") as fout:
        fout.write(change_events.model_dump_json())
    return change_events


@click.command()
def main():
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

    file_heatmap = file_heatmap_data(
        workspace_change_history=session_change_history,
        scratchpad=scratchpad,
        output_path=Path("file_heatmap_data.json"),
    )
    decl_heatmap = decl_heatmap_data(
        workspace_change_history=session_change_history,
        scratchpad=scratchpad,
        output_path=Path("decl_heatmap_data.json"),
    )
    write_session_data(
        owner="rkthomps",
        repo="lean-time-m",
        sha="880d1ca2ed73bb4427396fd635e301934142a97c",
        file_heatmap=file_heatmap,
        decl_heatmap=decl_heatmap,
    )


if __name__ == "__main__":
    main()
