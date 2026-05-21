import re
import tomlkit

from typing import Optional, Iterable
import logging
import subprocess
from pathlib import Path

from lean_edits_analysis.common import SCRATCHPAD_LOC

logger = logging.getLogger(__name__)

_EXPECTED_MODIFIED_FILES: list[Path] = [
    Path("lakefile.toml"),
    Path("lakefile.lean"),
    Path("lake-manifest.json"),
]


def _get_compatible_version(lean_toolchain: str) -> str:
    """
    See https://github.com/rkthomps/llm-instruments for compatibility
    """
    toolchain_match = re.match(
        r"^leanprover/lean4:v4\.(\d\d)\.(\d)-(rc\d+)?$", lean_toolchain
    )
    if not toolchain_match:
        nightly_match = re.match(
            r"^leanprover/lean4:nightly-\d{4}-\d{2}-\d{2}$", lean_toolchain
        )
        if nightly_match:
            return "main"
        raise ValueError(
            f"Unexpected lean toolchain format: {lean_toolchain}. Expected format: 'leanprover/lean4:v4.xx.x'"
        )
    minor_version_str = toolchain_match.groups()[0]
    minor_version = int(minor_version_str)
    if minor_version < 10:
        raise ValueError(
            f"Unsupported lean version {lean_toolchain}. Expected  >= v4.10."
        )
    if minor_version < 18:
        return "4.10.0"
    if minor_version < 22:
        return "4.18.0"
    if minor_version < 24:
        return "4.22.0"
    if minor_version < 25:
        return "4.24.0"
    if minor_version < 27:
        return "4.25.0"
    if minor_version < 29:
        return "4.27.0"
    return "main"


def _get_llm_instruments_branch(lean_toolchain_path: Path) -> str:
    contents = lean_toolchain_path.read_text()
    lean_toolchain = contents.strip()
    return _get_compatible_version(lean_toolchain)


def _add_instruments_to_lakefile_lean(lakefile_path: Path, compatible_branch: str):
    assert (
        lakefile_path.suffix == ".lean"
    ), f"Expected a .lean file, got {lakefile_path}"
    require_line = f'require «llm-instruments» from git "https://github.com/rkthomps/llm-instruments" @ "{compatible_branch}"'
    text = lakefile_path.read_text()

    if "llm-instruments" in text:
        return

    sep = "\n\n" if text.endswith("\n") else "\n\n"
    if text.endswith("\n\n"):
        sep = ""
    lakefile_path.write_text(text + sep + require_line + "\n")


def _add_instruments_to_lakefile_toml(
    lakefile_path: Path, compatible_branch: str
) -> None:
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
    entry["rev"] = compatible_branch
    requires.append(entry)

    lakefile_path.write_text(tomlkit.dumps(doc))


def _run(
    command: list[str], cwd: Optional[Path] = None, check: bool = True, stream=False
) -> subprocess.CompletedProcess[str]:
    """Returns true if the command ran successfully, false otherwise."""
    try:
        if not stream:
            output = subprocess.run(
                command,
                cwd=cwd,
                check=check,
                capture_output=True,
                text=True,
            )
            return output
        else:
            logger.info(f"Running command: {' '.join(command)} in {cwd}")
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
                text=True,
            )
            lines: list[str] = []
            assert process.stdout is not None  # for type checker
            for line in process.stdout:
                lines.append(line)
                logger.info(f"  {line.strip()}")
            rc = process.wait()
            output = "".join(lines)
            if check and rc != 0:
                raise subprocess.CalledProcessError(rc, command, output=output)
            return subprocess.CompletedProcess(command, rc, stdout=output)
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

    def _modified_files(self) -> Iterable[Path]:
        result = _run(
            ["git", "diff", "--name-only", "HEAD"],
            cwd=self.repo_path,
        )
        return (Path(line) for line in result.stdout.splitlines() if line)

    def restore(self):
        for file in self._modified_files():
            if file in _EXPECTED_MODIFIED_FILES:
                continue
            _run(["git", "restore", str(file)], cwd=self.repo_path)

    def write_version(self, files: dict[Path, str]):
        for file_relpath, contents in files.items():
            file_path = (self.repo_path / file_relpath).resolve()
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(contents)

    def _get_current_sha(self) -> str:
        result = _run(["git", "rev-parse", "HEAD"], cwd=self.repo_path)
        return result.stdout.strip()

    def _clone_and_checkout(self):
        self.owner_path.mkdir(parents=True, exist_ok=True)
        if not self.repo_path.exists():
            logger.info(f"Cloning {self.repo_url} into scratchpad")
            _run(["git", "clone", self.repo_url, self.repo_name], cwd=self.owner_path)

        assert self.repo_path.exists(), f"Failed to clone repo to {self.repo_path}"
        sha = self._get_current_sha()
        if sha != self.commit_sha:
            logger.info(f"Fetching commit {self.commit_sha} for {self.repo_url}")
            _run(["git", "fetch", "origin", self.commit_sha], cwd=self.repo_path)
            assert self.repo_path.exists(), f"Failed to clone repo to {self.repo_path}"
            _run(["git", "restore", "."], cwd=self.repo_path)
            _run(["git", "checkout", self.commit_sha], cwd=self.repo_path)
        sha = self._get_current_sha()
        assert (
            sha == self.commit_sha
        ), f"Failed to checkout {self.commit_sha} for {self.repo_url}, currently at {sha}"
        logger.info(f"Checked out {self.repo_url} at commit {self.commit_sha}")

    def _add_instrumentation(self):
        lean_toolchain_path = self.repo_path / "lean-toolchain"
        if not lean_toolchain_path.exists():
            raise ValueError(f"lean-toolchain file not found in {self.repo_path}")
        compatible_branch = _get_llm_instruments_branch(lean_toolchain_path)
        logger.info(
            f"Using llm-instruments branch {compatible_branch} for lean toolchain in {self.repo_url}"
        )
        lakefile_toml = self.repo_path / "lakefile.toml"
        if lakefile_toml.exists():
            logger.info(f"Adding llm-instruments to {lakefile_toml}")
            _add_instruments_to_lakefile_toml(lakefile_toml, compatible_branch)
            return
        lakefile_lean = self.repo_path / "lakefile.lean"
        if lakefile_lean.exists():
            logger.info(f"Adding llm-instruments to {lakefile_lean}")
            _add_instruments_to_lakefile_lean(lakefile_lean, compatible_branch)
            return
        raise ValueError(
            f"Could not find lakefile.toml or lakefile.lean in {self.repo_path}"
        )

    def _lake_update(self):
        _run(["lake", "update", "llm-instruments"], cwd=self.repo_path, stream=True)
        logger.info(
            f"Ran 'lake update' for {self.repo_url} at commit {self.commit_sha}"
        )
        logger.info(
            f"Running llm-instruments heartbeat for {self.repo_url} at commit {self.commit_sha}"
        )
        _run(["lake", "exe", "llm-instruments", "heartbeat"], cwd=self.repo_path)
        logger.info(
            f"Building llm-instruments-server for {self.repo_url} at commit {self.commit_sha}"
        )
        _run(["lake", "build", "llm-instruments-server"], cwd=self.repo_path)

    def _lake_build(self):
        logger.info(
            f"Building {self.repo_url} at commit {self.commit_sha} with llm-instruments"
        )
        result = _run(["lake", "build"], cwd=self.repo_path, check=False, stream=True)
        if result.returncode != 0:
            logger.error(
                f"Build failed for {self.repo_url} at commit {self.commit_sha}. Stderr:\n{result.stderr}"
            )
        else:
            logger.info(f"Built {self.repo_url} at commit {self.commit_sha}.")

    def setup(self):
        self._clone_and_checkout()  # Idempotent
        self._add_instrumentation()
        self._lake_update()
        self._lake_build()
