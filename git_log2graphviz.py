"""Generate a Graphviz commit graph for TinyWeatherForecastGermany."""

import shutil
from html import escape

# Graphviz is invoked with a fixed argument list and never through a shell.
import subprocess  # nosec B404
from collections.abc import Iterable, Mapping
from multiprocessing import cpu_count
from pathlib import Path
from typing import Any

import orjson
from pydriller import Repository
import regex

UPSTREAM_URL = "https://codeberg.org/Starfish/TinyWeatherForecastGermany"


def load_fork_urls(forks_file: Path) -> dict[str, str]:
    """Load Codeberg HTML URLs indexed by their local Git remote names.

    Args:
        forks_file (Path): Path to the JSON file created by the fork fetch step.

    Returns:
        urls (dict[str, str]): A mapping from names such as `fork_123` to Codeberg repository URLs.
    """
    if not forks_file.exists():
        return {}

    forks = orjson.loads(forks_file.read_bytes())
    return {
        f"fork_{fork['id']}": str(fork.get("html_url") or fork["clone_url"].removesuffix(".git")).rstrip("/")
        for fork in forks
    }


def get_commit_url(branches: Iterable[str], fork_urls: Mapping[str, str]) -> str | None:
    """Find a repository URL for a commit based on its containing branches.

    Args:
        branches: Git branch refs containing the commit.
        fork_urls: Fork repository URLs indexed by local remote name.

    Returns:
        The commit URL prefix, or `None` when no known remote contains it.
    """
    remote_names = {branch.removeprefix("remotes/").partition("/")[0] for branch in branches}
    if "origin" in remote_names:
        return f"{UPSTREAM_URL}/commit/"

    for remote_name in sorted(remote_names):
        if remote_name in fork_urls:
            return f"{fork_urls[remote_name].rstrip('/')}/commit/"
    return None


def _quote_dot_string(value: object) -> str:
    """Escape a value as a quoted Graphviz string."""
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\r", "").replace("\n", "\\n").replace("\t", "\\t")
    return f'"{escaped}"'


def _normalize_branch(branch: str) -> str:
    """Normalize a PyDriller branch name to its Git remote ref."""
    return branch.removeprefix("remotes/").split(" -> ", maxsplit=1)[0]


def _branch_heads(branch: str, commits: list[dict[str, Any]]) -> list[str]:
    """Return commits at the tips of a branch represented in commit data."""
    branch_commits = [
        commit for commit in commits if branch in {_normalize_branch(name) for name in commit["branches"]}
    ]
    branch_hashes = {commit["hash"] for commit in branch_commits}
    parent_hashes = {parent for commit in branch_commits for parent in commit["parents"] if parent in branch_hashes}
    return sorted(branch_hashes - parent_hashes)


def _repository_tooltip(repository: Mapping[str, Any], branches: list[str]) -> str:
    """Format fork API fields as detailed Graphviz tooltip text."""
    owner = repository.get("owner") or {}
    parent = repository.get("parent") or {}
    topics = repository.get("topics") or []
    details = [
        f"API ID: {repository.get('id', '')}",
        f"Repository: {repository.get('full_name', '')}",
        f"Owner: {owner.get('login', '')}",
        f"Fork of: {parent.get('full_name') or 'None'}",
        f"Default branch: {repository.get('default_branch', '')}",
        f"Language: {repository.get('language') or 'Unknown'}",
        f"Created: {repository.get('created_at', '')}",
        f"Updated: {repository.get('updated_at', '')}",
        f"Size: {repository.get('size', 0)} KB",
        f"Stars: {repository.get('stars_count', 0)}",
        f"Forks: {repository.get('forks_count', 0)}",
        f"Watchers: {repository.get('watchers_count', 0)}",
        f"Open issues: {repository.get('open_issues_count', 0)}",
        f"Open pull requests: {repository.get('open_pr_counter', 0)}",
        f"Archived: {repository.get('archived', False)}",
        f"Topics: {', '.join(str(topic) for topic in topics)}",
        f"Fetched branches: {', '.join(branches) or 'None'}",
        f"Description: {repository.get('description') or ''}",
    ]
    return "\n".join(details)


def build_repository_graph_elements(forks: list[dict[str, Any]], commits: list[dict[str, Any]]) -> tuple[str, str]:
    """Create repository nodes and branch-tip edges for upstream and forks.

    Args:
        forks: Fork API records, including their upstream parent metadata.
        commits: Commit dictionaries containing branch names and parent hashes.

    Returns:
        DOT declarations for repository nodes and their branch-tip edges.
    """
    normalized_branches = {
        _normalize_branch(branch) for commit in commits for branch in commit["branches"] if " -> " not in branch
    }
    upstream = next(
        (fork.get("parent") for fork in forks if fork.get("parent")),
        {
            "full_name": "Starfish/TinyWeatherForecastGermany",
            "html_url": UPSTREAM_URL,
            "default_branch": "master",
        },
    )
    repositories = [("upstream_repository", upstream, "origin")]
    repositories.extend((f"fork_repository_{fork['id']}", fork, f"fork_{fork['id']}") for fork in forks)

    node_lines = [
        "\tsubgraph cluster_repositories {",
        '\t\tlabel="Codeberg repositories";',
        '\t\tstyle="rounded";',
        '\t\tcolor="#9aa8b5";',
    ]
    edge_lines = []

    for node_id, repository, remote_name in repositories:
        default_branch = str(repository.get("default_branch") or "master")
        remote_prefix = f"{remote_name}/"
        branches = sorted(
            branch[len(remote_prefix) :] for branch in normalized_branches if branch.startswith(remote_prefix)
        )
        full_name = str(repository.get("full_name") or node_id)
        label = f"{full_name}\n{len(branches)} branches"
        url = str(repository.get("html_url") or repository.get("clone_url", "").removesuffix(".git"))
        tooltip = _repository_tooltip(repository, branches)
        node_lines.append(
            f"\t\t{_quote_dot_string(node_id)} "
            f"[label={_quote_dot_string(label)}, shape=folder, "
            'style="filled", fillcolor="#eaf2f8", color="#526777", '
            f"URL={_quote_dot_string(url)}, "
            f"tooltip={_quote_dot_string(tooltip)}];"
        )

        for branch in branches:
            remote_branch = f"{remote_name}/{branch}"
            for head_hash in _branch_heads(remote_branch, commits):
                default_label = " (default)" if branch == default_branch else ""
                edge_lines.append(
                    f"\t{_quote_dot_string(head_hash)} -> "
                    f"{_quote_dot_string(node_id)} "
                    f"[label={_quote_dot_string(branch + default_label)}, "
                    'style="dashed", color="#718696"];'
                )

    node_lines.append("\t}")
    return "\n".join(node_lines), "\n".join(edge_lines)


def main(project_dir: Path | None = None) -> None:
    """Write commit data and render the repository history as an SVG.

    Args:
        project_dir: Directory for repository inputs and generated graph files.
            Defaults to the directory containing this script.
    """
    parent_dir = project_dir or Path(__file__).parent
    forks_file = parent_dir / "forks-api.json"
    forks = orjson.loads(forks_file.read_bytes()) if forks_file.exists() else []
    fork_urls = load_fork_urls(forks_file)
    commits_list = []
    dot_graph_1 = """
digraph G {
"""
    dot_graph_2 = ""

    for commit in Repository(
        parent_dir / "TinyWeatherForecastGermany",
        include_remotes=True,
        num_workers=cpu_count(),
    ).traverse_commits():
        commit_dict = {
            "hash": str(commit.hash),
            "msg": str(commit.msg).replace('"', "'"),
            "timestamp": str(commit.committer_date),
            "author_name": str(commit.author.name),
            "branches": list(commit.branches),
            "parents": list(commit.parents),
            "merge": commit.merge,
        }

        c_color = ""
        if commit_dict["merge"]:
            c_color = ",color=blue"

        if " using weblate" in commit_dict["msg"].lower():
            c_color = ",color=darkgreen"

        branch_names = ", ".join(sorted(commit_dict["branches"]))
        commit_hash = commit_dict["hash"]
        commit_timestamp = commit_dict["timestamp"]
        author_name = escape(commit_dict["author_name"])
        dot_graph_1 += (
            f"\t{_quote_dot_string(commit_hash)} "
            f"[label=<<B>{commit_hash[:6]}</B>{author_name}>, "
            f"comment={_quote_dot_string(commit_timestamp)},"
        )
        tooltip = f"{commit_timestamp}\n{commit_dict['msg']}\nBranches: {branch_names}"
        dot_graph_1 += f" tooltip={_quote_dot_string(tooltip)}, shape=box{c_color},"

        commit_url = get_commit_url(commit_dict["branches"], fork_urls)
        if commit_url:
            dot_graph_1 += f" URL={_quote_dot_string(commit_url + commit_hash)}"

        dot_graph_1 += "];\n"

        for c_parent in commit_dict["parents"]:
            dot_graph_2 += f"\t {_quote_dot_string(c_parent)} -> " f"{_quote_dot_string(commit_hash)};\n"

        commits_list.append(commit_dict)

    repository_nodes, repository_edges = build_repository_graph_elements(forks, commits_list)
    dot_graph_1 += "\n" + repository_nodes
    dot_graph_2 += repository_edges

    (parent_dir / "commit_list.json").write_bytes(orjson.dumps(commits_list, option=orjson.OPT_INDENT_2))

    dot_graph_1 += "\n\n" + dot_graph_2 + "}"
    dot_file = parent_dir / "git_graph.dot"
    with open(dot_file, "w", encoding="utf-8") as fh:
        fh.write(dot_graph_1)

    svg_file = parent_dir / "git_graph.svg"
    dot_executable = shutil.which("dot")
    if dot_executable is None:
        raise FileNotFoundError("Graphviz 'dot' executable was not found on PATH")
    # Paths are passed as separate arguments; shell interpretation is disabled.
    subprocess.run(  # nosec B603
        [dot_executable, "-Tsvg", "-o", str(svg_file), str(dot_file)],
        check=True,
    )

    with open(svg_file, "r", encoding="utf-8") as fh:
        svg_contents = fh.read()

    svg_contents = regex.sub(
        r"(?im)^[ \t]*<!--[\w ?&#;,:+]*-->[ \t]*\r?\n?",
        "",
        svg_contents,
    )

    with open(svg_file, "w", encoding="utf-8") as fh:
        fh.write(svg_contents)


if __name__ == "__main__":
    main()
