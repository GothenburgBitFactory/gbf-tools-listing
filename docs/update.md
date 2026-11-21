# Update a tools listing

How to regenerate a tools listing locally, for example to preview a blacklist or include change before opening a PR.
The listings are updated daily by CI; do this manually only when needed.

## Prerequisites

The tool currently scrapes GitHub only, so the only credential needed is a GitHub token.
Generate one and store it safely for later:

* [GitHub](https://github.com/settings/tokens): requires no special scopes

Install [`uv`](https://github.com/astral.sh/uv) if you don't have it yet:

```bash
$ curl -LsSf https://astral.sh/uv/install.sh | sh
```

Set the `GITHUB_API_KEY` environment variable (or export it in a wrapper script that **must not be committed**).

## Update the listing

```bash
$ GITHUB_API_KEY=... uv run tools-list update <project>
```

`<project>` is the project directory — currently `task` (Taskwarrior) or `timew` (Timewarrior).

`uv` will automatically create the project environment (`.venv/`, not committed) from `pyproject.toml`, install the `tools-list` package with its dependencies, and invoke it.

On execution, the tool scrapes GitHub for repositories matching the topics configured in `config.json`.
The listing is written to the file named by the project's `output` config field.

## How the sources work

`update` regenerates the listing by merging all configured sources:

* The **github** source searches GitHub for repositories that have one of the project's `keywords` (see its `config.json`) as a topic.
* The **manual** source adds hand-curated entries verbatim.

Each source also takes its part of the project's `include.json`, which defines per source which URLs should be included in addition:

* `"github"` — GitHub repositories that are not picked up by the topic search, fetched by full repository name.
* `"manual"` — repositories hosted on other providers than GitHub, included verbatim.

Includes are the exception, not the rule: a repository owner who wants their tool listed on the tools page should simply add one of the configured topics to their GitHub repository — the next update picks it up.

To filter out a tool, add its URL (with a reason) to the project's `blacklist.json` — or use the interactive [review](review.md) command.

Commit the changes and open a PR; CI picks up the changes on the next run.

## Optional configuration

* `LOG_LEVEL` — set to `DEBUG` (or `TRACE`/`WARN`/`ERROR`) to control log verbosity.
  Defaults to `INFO`.
