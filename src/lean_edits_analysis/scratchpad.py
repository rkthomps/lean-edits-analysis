import tomlkit

from typing import Optional
import logging
import subprocess
from pathlib import Path

from lean_edits_analysis.common import SCRATCHPAD_LOC

logger = logging.getLogger(__name__)


def _add_instruments_to_lakefile_lean(lakefile_path: Path):
    assert (
        lakefile_path.suffix == ".lean"
    ), f"Expected a .lean file, got {lakefile_path}"
    require_line = 'require «llm-instruments» from git "https://github.com/rkthomps/llm-instruments" @ "main"'
    text = lakefile_path.read_text()

    if "llm-instruments" in text:
        return

    sep = "\n\n" if text.endswith("\n") else "\n\n"
    if text.endswith("\n\n"):
        sep = ""
    lakefile_path.write_text(text + sep + require_line + "\n")


def _add_instruments_to_lakefile_toml(lakefile_path: Path) -> None:
    doc = tomlkit.parse(lakefile_path.read_text())

    requires = doc.get("require")
    if requires is None:
        requires = tomlkit.aot()
        doc["require"] = requires

    if any(r.get("name") == "llm-instruments" for r in requires):
        return  # already present

    entry = tomlkit.table()
    entry["name"] = "llm-instruments"
    entry["git"] = "https://github.com/rkthomps/llm-instruments.git"
    entry["rev"] = "main"
    requires.append(entry)

    lakefile_path.write_text(tomlkit.dumps(doc))


def _run(command: list[str], cwd: Optional[Path] = None, check: bool = True) -> bool:
    """Returns true if the command ran successfully, false otherwise."""
    try:
        output = subprocess.run(
            command,
            cwd=cwd,
            check=check,
            capture_output=True,
            text=True,
        )
        return output.returncode == 0
    except subprocess.CalledProcessError as e:
        logger.exception(f"Command '{' '.join(command)}' failed: {e}")
        raise


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

    def clone_and_checkout(self):
        self.owner_path.mkdir(parents=True, exist_ok=True)
        if not self.repo_path.exists():
            logger.info(f"Cloning {self.repo_url} into scratchpad")
            _run(["git", "clone", self.repo_url, self.repo_name], cwd=self.owner_path)
        else:
            logger.info(f"Fetching latest changes for {self.repo_url}")
            _run(["git", "fetch"], cwd=self.repo_path)

        assert self.repo_path.exists(), f"Failed to clone repo to {self.repo_path}"
        _run(["git", "restore", "."], cwd=self.repo_path)
        _run(["git", "checkout", self.commit_sha], cwd=self.repo_path)

    def add_instrumentation(self):
        lakefile_toml = self.repo_path / "lakefile.toml"
        if lakefile_toml.exists():
            logger.info(f"Adding llm-instruments to {lakefile_toml}")
            _add_instruments_to_lakefile_toml(lakefile_toml)
            return
        lakefile_lean = self.repo_path / "lakefile.lean"
        if lakefile_lean.exists():
            logger.info(f"Adding llm-instruments to {lakefile_lean}")
            _add_instruments_to_lakefile_lean(lakefile_lean)
            return
        raise ValueError(
            f"Could not find lakefile.toml or lakefile.lean in {self.repo_path}"
        )

    def lake_update(self):
        _run(["lake", "update"], cwd=self.repo_path)
        logger.info(
            f"Ran 'lake update' for {self.repo_url} at commit {self.commit_sha}"
        )
        logger.info(
            f"Running llm-instruments heartbeat for {self.repo_url} at commit {self.commit_sha}"
        )
        _run(["lake", "exe", "llm-instruments", "heartbeat"], cwd=self.repo_path)

    def lake_build(self):
        result = _run(["lake", "build"], cwd=self.repo_path, check=False)
        logger.info(
            f"Built {self.repo_url} at commit {self.commit_sha}. Success: {result}"
        )

    def setup(self):
        self.clone_and_checkout()
        self.add_instrumentation()
        self.lake_update()
        self.lake_build()
