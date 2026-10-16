"""Discover Codeberg forks and fetch their branches into the upstream clone."""

import shutil

# Git is invoked with argument lists and never through a shell.
import subprocess  # nosec B404
from pathlib import Path
from typing import Any

import orjson
import requests

FORKS_API_URL = "https://codeberg.org/api/v1/repos/Starfish/TinyWeatherForecastGermany/forks"
PAGE_SIZE = 50
PROJECT_DIR = Path(__file__).parent
REPOSITORY_PATH = PROJECT_DIR / "TinyWeatherForecastGermany"
FORKS_JSON_PATH = PROJECT_DIR / "forks-api.json"


def fetch_forks() -> list[dict[str, Any]]:
    """Fetch every page of fork metadata from the Codeberg API.

    Returns:
        Fork metadata dictionaries returned by Codeberg.

    Raises:
        requests.HTTPError: If Codeberg returns an unsuccessful response.
        ValueError: If the API response is not a JSON array.
    """
    forks = []
    page = 1

    while True:
        response = requests.get(
            FORKS_API_URL,
            params={"page": page, "limit": PAGE_SIZE},
            timeout=30,
        )
        response.raise_for_status()
        page_forks = orjson.loads(response.content)
        if not isinstance(page_forks, list):
            raise ValueError("Codeberg fork API response must be a JSON array")

        forks.extend(page_forks)
        if len(page_forks) < PAGE_SIZE:
            return forks
        page += 1


def integrate_forks(forks: list[dict[str, Any]], repository_path: Path) -> None:
    """Fetch fork branches into the upstream repository as named remotes.

    Args:
        forks: Fork records returned by the Codeberg API.
        repository_path: Path to the local upstream Git repository.

    Raises:
        FileNotFoundError: If Git is not available on ``PATH``.
        subprocess.CalledProcessError: If remote setup or fetching fails.
    """
    git_executable = shutil.which("git")
    if git_executable is None:
        raise FileNotFoundError("Git executable was not found on PATH")

    for fork in forks:
        remote_name = f"fork_{fork['id']}"
        clone_url = str(fork["clone_url"])
        # Git receives discrete arguments; no value is interpreted by a shell.
        remote = subprocess.run(  # nosec B603
            [
                git_executable,
                "-C",
                str(repository_path),
                "remote",
                "get-url",
                remote_name,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if remote.returncode == 0:
            command = [
                git_executable,
                "-C",
                str(repository_path),
                "remote",
                "set-url",
                remote_name,
                clone_url,
            ]
        else:
            command = [
                git_executable,
                "-C",
                str(repository_path),
                "remote",
                "add",
                remote_name,
                clone_url,
            ]
        subprocess.run(command, check=True)  # nosec B603

    subprocess.run(  # nosec B603
        [
            git_executable,
            "-C",
            str(repository_path),
            "fetch",
            "--all",
            "--prune",
        ],
        check=True,
    )


def main() -> None:
    """Fetch fork metadata and integrate all fork refs into the main clone."""
    forks = fetch_forks()
    FORKS_JSON_PATH.write_bytes(orjson.dumps(forks, option=orjson.OPT_INDENT_2))
    integrate_forks(forks, REPOSITORY_PATH)


if __name__ == "__main__":
    main()
