import logging
import click
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from edit_data.types import GitChangeMetadata, WorkspaceChangeHistory

from lean_edits_analysis.data import (
    RepoMetadata,
    load_matching_sessions,
    load_matching_commit_sessions,
    find_repo_metadata,
)
from lean_edits_analysis.util import git_url_parts_from_session
from lean_edits_analysis.scratchpad import Scratchpad
from lean_edits_analysis.edit_info import cache_repo_iter, get_repo_lock, need_to_cache

from lean_edits_analysis.visualize.build import write_session_data
from lean_edits_analysis.visualize.file_heat_map import FileHeatmapInfo
from lean_edits_analysis.visualize.decl_heat_map import DeclHeatmapInfo

logger = logging.getLogger(__name__)


@click.group()
def cli():
    pass


@click.command()
@click.argument("repo_owner", type=str)
@click.argument("repo_name", type=str)
@click.argument("commit_sha", type=str)
def commit(
    repo_owner: str,
    repo_name: str,
    commit_sha: str,
):
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    logging.getLogger("lean_edits_analysis").setLevel(logging.INFO)
    logging.getLogger("__name__").setLevel(logging.INFO)

    session = load_matching_commit_sessions(
        repo_owner=repo_owner,
        repo_name=repo_name,
        commit_sha=commit_sha,
    )

    git_url_parts = git_url_parts_from_session(session)
    assert (
        git_url_parts is not None
    ), "Failed to parse git URL parts from session metadata."

    scratchpad = Scratchpad(
        repo_owner=git_url_parts.owner,
        repo_name=git_url_parts.repo,
        commit_sha=commit_sha,
    )

    file_heatmap = FileHeatmapInfo.build(session, scratchpad)
    decl_heatmap = DeclHeatmapInfo.build(session, scratchpad)

    write_session_data(
        owner=git_url_parts.owner,
        repo=git_url_parts.repo,
        sha=commit_sha,
        file_heatmap=file_heatmap,
        decl_heatmap=decl_heatmap,
    )


def _show_session(session: WorkspaceChangeHistory):
    git_parts = git_url_parts_from_session(session)
    if git_parts is None:
        return
    assert isinstance(session.metadata, GitChangeMetadata)
    with get_repo_lock(git_parts.owner, git_parts.repo):
        scratchpad = Scratchpad(
            repo_owner=git_parts.owner,
            repo_name=git_parts.repo,
            commit_sha=session.metadata.head,
        )
        scratchpad.setup()
        file_heatmap = FileHeatmapInfo.build(session, scratchpad)
        decl_heatmap = DeclHeatmapInfo.build(session, scratchpad)
        write_session_data(
            owner=git_parts.owner,
            repo=git_parts.repo,
            sha=session.metadata.head,
            file_heatmap=file_heatmap,
            decl_heatmap=decl_heatmap,
        )


def _session_num_edits(session: WorkspaceChangeHistory) -> int:
    return sum(len(file.edits_history) for file in session.files)


def _cache_and_show_repo(repo_metadata: RepoMetadata):
    for session, success in cache_repo_iter(
        repo_metadata.repo_owner, repo_metadata.repo_name
    ):
        logger.info(
            f"Finished caching session for {repo_metadata.repo_owner}/{repo_metadata.repo_name} with success={success}"
        )
        if _session_num_edits(session) == 0:
            continue
        if success:
            with get_repo_lock(repo_metadata.repo_owner, repo_metadata.repo_name):
                assert isinstance(session.metadata, GitChangeMetadata)
                scratchpad = Scratchpad(
                    repo_owner=repo_metadata.repo_owner,
                    repo_name=repo_metadata.repo_name,
                    commit_sha=session.metadata.head,
                )
                logger.info(
                    f"Generating file heatmap for {repo_metadata.repo_owner}/{repo_metadata.repo_name} at commit {session.metadata.head}"
                )
                file_heatmap = FileHeatmapInfo.build(session, scratchpad)
                logger.info(
                    f"Generating decl heatmap for {repo_metadata.repo_owner}/{repo_metadata.repo_name} at commit {session.metadata.head}"
                )
                decl_heatmap = DeclHeatmapInfo.build(session, scratchpad)
                logger.info(
                    f"Writing session data for {repo_metadata.repo_owner}/{repo_metadata.repo_name} at commit {session.metadata.head}"
                )
                write_session_data(
                    owner=repo_metadata.repo_owner,
                    repo=repo_metadata.repo_name,
                    sha=session.metadata.head,
                    file_heatmap=file_heatmap,
                    decl_heatmap=decl_heatmap,
                )
                logger.info(
                    f"Finished processing session for {repo_metadata.repo_owner}/{repo_metadata.repo_name} at commit {session.metadata.head}"
                )


def _setup_logging():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    # Formatter
    formatter = logging.Formatter("%(asctime)s %(name)s %(levelname)s %(message)s")

    # File handler
    date_str = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    Path("logs").mkdir(exist_ok=True)
    fh = logging.FileHandler(f"logs/cache-and-show-{date_str}.log")
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)

    # Stdout handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)

    # Add both to root logger
    root = logging.getLogger()
    root.addHandler(fh)
    root.addHandler(ch)

    # Set specific loggers
    logging.getLogger("lean_edits_analysis").setLevel(logging.INFO)
    logging.getLogger(__name__).setLevel(logging.INFO)


@cli.command()
def show():
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    logging.getLogger("lean_edits_analysis").setLevel(logging.INFO)
    logging.getLogger(__name__).setLevel(logging.INFO)
    repo_metadata = find_repo_metadata()

    for repo in repo_metadata:
        logger.info(
            f"Repo {repo.repo_owner}/{repo.repo_name} has {len(repo.sessions)} sessions and {repo.total_edits} edits"
        )
        for session in load_matching_sessions(repo.repo_owner, repo.repo_name):
            if not isinstance(session.metadata, GitChangeMetadata):
                continue
            if _session_num_edits(session) == 0:
                continue
            if not need_to_cache(
                repo.repo_owner, repo.repo_name, session.metadata.head, session
            ):
                logger.info(
                    f"showing session for {repo.repo_owner}/{repo.repo_name} at commit {session.metadata.head}"
                )
                _show_session(session)


@cli.command()
@click.option(
    "--workers",
    default=1,
    help="Number of worker threads to use for caching and processing.",
)
def cache_and_show(workers: int):
    _setup_logging()
    repo_metadata = find_repo_metadata()

    for repo in repo_metadata:
        logger.info(
            f"Repo {repo.repo_owner}/{repo.repo_name} has {len(repo.sessions)} sessions and {repo.total_edits} edits"
        )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_cache_and_show_repo, repo): repo for repo in repo_metadata
        }
        for future in as_completed(futures):
            repo = futures[future]
            try:
                future.result()
            except Exception as e:
                logger.exception(
                    f"Error processing {repo.repo_owner}/{repo.repo_name}: {e}"
                )


if __name__ == "__main__":
    cli()
