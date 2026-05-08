import logging
import subprocess
from pathlib import Path

from lean_edits_analysis.common import SCRATCHPAD_LOC

logger = logging.getLogger(__name__)


class Scratchpad:
    def __init__(self, repo_owner: str, repo_name: str, commit_sha: str):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.commit_sha = commit_sha

    @property
    def repo_url(self) -> str:
        return f"https://github.com/{self.repo_owner}/{self.repo_name}.git"

    @property
    def owner_path(self) -> Path:
        return SCRATCHPAD_LOC / self.repo_owner

    @property
    def repo_path(self) -> Path:
        return self.owner_path / self.repo_name

    def setup(self):
        if not self.repo_path.exists():
            self.owner_path.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", self.repo_url, self.repo_name],
                cwd=self.owner_path,
                check=True,
            )
        assert self.repo_path.exists(), f"Failed to clone repo to {self.repo_path}"
        subprocess.run(
            ["git", "checkout", self.commit_sha],
            cwd=self.repo_path,
            check=True,
        )
        logger.info(f"Checked out {self.repo_url} at commit {self.commit_sha}")
