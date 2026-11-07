# git-graph

Fetch all commits of [**TinyWeatherForecastGermany**](https://codeberg.org/Starfish/TinyWeatherForecastGermany/) and draw a graph for them using Graphviz.

Fork branches are fetched into the upstream repository and included in the graph. Fork-only commits link to their Codeberg repository, and branch names appear in each commit's tooltip.

The results are located at the `pages` branch and also published using GitHub Pages.

- [`git_graph.svg`](https://tinyweatherforecastgermanygroup.github.io/git-graph/git_graph.svg)
- [`git_graph.dot`](https://tinyweatherforecastgermanygroup.github.io/git-graph/git_graph.dot)

**Merge** commits are highlighted in blue.  
**Weblate** commits are highlighted in dark green.

**status**: work in progress

**author**: Jean-Luc Tibaux

## Development setup

Requirements: Python 3.11 or newer, Git, Graphviz, and [uv](https://docs.astral.sh/uv/).

```sh
uv sync --all-groups
git clone https://codeberg.org/Starfish/TinyWeatherForecastGermany.git
uv run python __init__.py
uv run python git_log2graphviz.py
```

The first script discovers forks and fetches their branches as named remotes. The
second writes `commit_list.json`, `git_graph.dot`, and `git_graph.svg` in the
project directory.

## Testing

Install the locked development dependencies and run the test suite with:

```sh
uv sync --locked --all-groups
uv run pytest
```

Pytest reports coverage for fork integration and graph generation. The suite
requires at least 80% total coverage. Pull requests, including Dependabot pull
requests, run the same checks in GitHub Actions.

To upgrade runtime and development dependencies to their latest compatible
versions and refresh `uv.lock`, run:

```sh
uv lock --upgrade
uv sync --all-groups
```

The committed `uv.lock` keeps development and CI installations reproducible.
