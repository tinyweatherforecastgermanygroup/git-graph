"""Tests for fetching and visualizing repository forks."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import orjson
import pytest

import __init__ as fork_integration
import git_log2graphviz
from __init__ import fetch_forks, integrate_forks
from git_log2graphviz import (
    build_repository_graph_elements,
    get_commit_url,
    load_fork_urls,
    main,
)


def run_git(repository: Path, *arguments: str) -> str:
    """Run Git in a repository and return its standard output.

    Args:
        repository: Directory where the Git command runs.
        *arguments: Arguments passed to the Git executable.

    Returns:
        Standard output from the Git command.
    """
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def test_fetch_forks_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fetch all pages of forks using the Codeberg pagination parameters."""
    first_page = [{"id": fork_id} for fork_id in range(50)]
    second_page = [{"id": 50}]
    responses = [
        Mock(content=orjson.dumps(first_page)),
        Mock(content=orjson.dumps(second_page)),
    ]
    get = Mock(side_effect=responses)
    monkeypatch.setattr(fork_integration.requests, "get", get)

    forks = fetch_forks()

    assert len(forks) == 51
    assert forks[-1] == {"id": 50}
    assert get.call_args_list == [
        call(
            fork_integration.FORKS_API_URL,
            params={"page": 1, "limit": 50},
            timeout=30,
        ),
        call(
            fork_integration.FORKS_API_URL,
            params={"page": 2, "limit": 50},
            timeout=30,
        ),
    ]


def test_fetch_forks_rejects_non_array_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject an API payload that is valid JSON but not an array."""
    response = Mock(content=orjson.dumps({"error": "invalid response"}))
    monkeypatch.setattr(fork_integration.requests, "get", Mock(return_value=response))

    with pytest.raises(ValueError, match="JSON array"):
        fetch_forks()


def test_fetches_fork_branch_and_updates_named_remote(tmp_path: Path) -> None:
    """Fetch a fork branch and update its URL on subsequent runs."""
    fork_worktree = tmp_path / "fork-worktree"
    fork_worktree.mkdir()
    run_git(fork_worktree, "init", "--initial-branch=main")
    run_git(fork_worktree, "config", "user.name", "Test User")
    run_git(fork_worktree, "config", "user.email", "test@example.com")
    (fork_worktree / "README.md").write_text("fork\n", encoding="utf-8")
    run_git(fork_worktree, "add", "README.md")
    run_git(fork_worktree, "commit", "-m", "fork commit")

    fork_bare = tmp_path / "fork.git"
    subprocess.run(
        ["git", "clone", "--bare", str(fork_worktree), str(fork_bare)],
        check=True,
        capture_output=True,
        text=True,
    )
    upstream_repository = tmp_path / "upstream"
    upstream_repository.mkdir()
    run_git(upstream_repository, "init", "--initial-branch=main")
    fork = {"id": 42, "clone_url": str(fork_bare)}

    integrate_forks([fork], upstream_repository)
    integrate_forks([fork], upstream_repository)

    remote_branches = run_git(
        upstream_repository,
        "for-each-ref",
        "--format=%(refname:short)",
        "refs/remotes",
    ).splitlines()
    assert "fork_42/main" in remote_branches
    assert run_git(upstream_repository, "remote", "get-url", "fork_42").strip() == str(fork_bare)


def test_load_fork_urls_and_missing_file(tmp_path: Path) -> None:
    """Map fork API entries to remotes and tolerate absent metadata."""
    forks_file = tmp_path / "forks-api.json"
    forks_file.write_bytes(
        orjson.dumps(
            [
                {
                    "id": 42,
                    "html_url": "https://codeberg.org/example/fork/",
                    "clone_url": "https://codeberg.org/example/fork.git",
                }
            ]
        )
    )

    assert load_fork_urls(forks_file) == {"fork_42": "https://codeberg.org/example/fork"}
    assert load_fork_urls(tmp_path / "missing.json") == {}


def test_selects_commit_url_by_remote_precedence() -> None:
    """Prefer upstream URLs, then known forks, and omit unknown remotes."""
    fork_urls = {"fork_42": "https://codeberg.org/example/fork"}

    assert get_commit_url({"remotes/fork_42/main"}, fork_urls) == ("https://codeberg.org/example/fork/commit/")
    assert (
        get_commit_url({"remotes/origin/main", "remotes/fork_42/main"}, fork_urls)
        == "https://codeberg.org/Starfish/TinyWeatherForecastGermany/commit/"
    )
    assert get_commit_url({"remotes/unknown/main"}, fork_urls) is None


def test_repository_graph_includes_every_api_fork() -> None:
    """Render all API forks and include their metadata and branch heads."""
    upstream = {
        "full_name": "Starfish/TinyWeatherForecastGermany",
        "html_url": "https://codeberg.org/Starfish/TinyWeatherForecastGermany",
        "default_branch": "main",
    }
    forks = [
        {
            "id": 42,
            "full_name": "example/weather-fork",
            "html_url": "https://codeberg.org/example/weather-fork",
            "owner": {"login": "example"},
            "default_branch": "main",
            "updated_at": "2026-10-01T10:00:00Z",
            "language": "Python",
            "size": 12,
            "stars_count": 3,
            "forks_count": 1,
            "watchers_count": 4,
            "open_issues_count": 2,
            "open_pr_counter": 1,
            "archived": False,
            "topics": ["weather", "graph"],
            "description": "A test fork",
            "parent": upstream,
        },
        {
            "id": 43,
            "full_name": "another/empty-fork",
            "html_url": "https://codeberg.org/another/empty-fork",
            "owner": {"login": "another"},
            "default_branch": "main",
            "parent": upstream,
        },
    ]
    commits = [
        {
            "hash": "upstream-head",
            "parents": [],
            "branches": ["origin/main"],
        },
        {
            "hash": "fork-head",
            "parents": ["upstream-head"],
            "branches": ["fork_42/main", "fork_42/feature/weather"],
        },
    ]

    repository_nodes, branch_edges = build_repository_graph_elements(forks, commits)

    assert '"fork_repository_42"' in repository_nodes
    assert '"fork_repository_43"' in repository_nodes
    assert '"upstream_repository"' in repository_nodes
    assert "API ID: 42" in repository_nodes
    assert "example/weather-fork" in repository_nodes
    assert "Default branch: main" in repository_nodes
    assert "Fork of: Starfish/TinyWeatherForecastGermany" in repository_nodes
    assert "Updated: 2026-10-01T10:00:00Z" in repository_nodes
    assert "Topics: weather, graph" in repository_nodes
    assert "another/empty-fork\\n0 branches" in repository_nodes
    assert '"fork-head" -> "fork_repository_42"' in branch_edges
    assert '"fork-head" -> "fork_repository_42"' in branch_edges


def test_main_writes_graph_and_removes_svg_comment(tmp_path: Path) -> None:
    """Generate JSON, DOT, and cleaned SVG from fetched commit objects."""
    (tmp_path / "forks-api.json").write_bytes(
        orjson.dumps(
            [
                {
                    "id": 42,
                    "html_url": "https://codeberg.org/example/fork",
                    "clone_url": "https://codeberg.org/example/fork.git",
                }
            ]
        )
    )
    commits = [
        SimpleNamespace(
            hash="abcdef123456",
            msg="merge commit",
            committer_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
            author=SimpleNamespace(name="Author"),
            branches={"remotes/origin/main"},
            parents=[],
            merge=True,
        ),
        SimpleNamespace(
            hash="123456abcdef",
            msg="translation using Weblate",
            committer_date=datetime(2025, 1, 2, tzinfo=timezone.utc),
            author=SimpleNamespace(name="Translator"),
            branches={"remotes/fork_42/main"},
            parents=["abcdef123456"],
            merge=False,
        ),
    ]

    def render_svg(command: list[str], check: bool) -> None:
        """Write stub SVG output at Graphviz's output path."""
        assert check is True
        Path(command[3]).write_text("<!-- Generated by graphviz -->\n<svg/>\n", encoding="utf-8")

    with (
        patch.object(git_log2graphviz, "Repository") as repository,
        patch.object(git_log2graphviz.shutil, "which", return_value="/usr/bin/dot"),
        patch.object(git_log2graphviz.subprocess, "run", side_effect=render_svg),
    ):
        repository.return_value.traverse_commits.return_value = commits
        main(tmp_path)

    dot_graph = (tmp_path / "git_graph.dot").read_text(encoding="utf-8")
    svg = (tmp_path / "git_graph.svg").read_text(encoding="utf-8")
    commit_data = orjson.loads((tmp_path / "commit_list.json").read_bytes())

    assert "color=blue" in dot_graph
    assert "color=darkgreen" in dot_graph
    assert "Branches: remotes/fork_42/main" in dot_graph
    assert "https://codeberg.org/example/fork/commit/123456abcdef" in dot_graph
    assert '"abcdef123456" -> "123456abcdef"' in dot_graph
    assert "Generated by graphviz" not in svg
    assert svg == "<svg/>\n"
    assert len(commit_data) == 2


def test_main_fetches_and_persists_forks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Persist fetched fork metadata before integrating its remotes."""
    forks_path = tmp_path / "forks-api.json"
    forks = [{"id": 42, "clone_url": "https://codeberg.org/example/fork.git"}]
    integration = Mock()
    monkeypatch.setattr(fork_integration, "FORKS_JSON_PATH", forks_path)
    monkeypatch.setattr(fork_integration, "REPOSITORY_PATH", tmp_path / "repo")
    monkeypatch.setattr(fork_integration, "fetch_forks", Mock(return_value=forks))
    monkeypatch.setattr(fork_integration, "integrate_forks", integration)

    fork_integration.main()

    assert orjson.loads(forks_path.read_bytes()) == forks
    integration.assert_called_once_with(forks, tmp_path / "repo")
