# `tools-list` reference

CLI commands, environment variables, and the project config file.
The tool has no built-in notion of any specific project — everything project-specific is supplied via the project's `config.json`.

## Commands

| Command                       | Purpose                                                                                            |
|-------------------------------|----------------------------------------------------------------------------------------------------|
| `tools-list update <project>` | Regenerate the tools listing from all sources. See [Update a tools listing](update.md).            |
| `tools-list review <project>` | Interactively review new tools and the current blacklist. See [Review a tools listing](review.md). |
| `tools-list purge <project>`  | Purge blacklist for non-existent or renamed repositories.                                          |

`<project>` is the project directory holding the `config.json` and the files it names.

### `review --since DATE\|COMMIT`

Review tools added since that date (`YYYY-MM-DD`) or commit (an ancestor of `HEAD`) instead of since the recorded review commit.

### `purge`

The `purge` command checks every URL from the blacklist.
URLs returning a 404 remove the entry, renamed repositories are updated to their new URL, any other error aborts the run.
No GitHub API token and no git repository are required.
The updated blacklist is written back but not committed — commit the changes when ready.

The update workflows run a purge before each scheduled update and commit the result before regenerating the listing, so the latter always runs with a purged blacklist; a failed purge does not block the update.

## Sources

`update` regenerates the listing by merging all configured sources — `github` (topic search) and `manual` (verbatim entries) today.
See [Update a tools listing](update.md) for how they work together with the project's includes.

GitHub is the only source today, so `GITHUB_API_KEY` is the only credential the tool needs.
Other repository hosting services are planned: the source interface (`tools_list/sources/`) is designed to make adding one straightforward.

## Environment variables

| Variable         | Purpose                                                           |
|------------------|-------------------------------------------------------------------|
| `GITHUB_API_KEY` | GitHub API token, required by `update`. No special scopes needed. |
| `LOG_LEVEL`      | `TRACE`/`DEBUG`/`INFO`/`WARN`/`ERROR`. Defaults to `INFO`.        |

## Config file

Each project directory contains a `config.json` that supplies all the script's inputs:

```json
{
  "blacklist": "blacklist.json",
  "includes": "include.json",
  "output": "tools-data.json",
  "keywords": ["kw1", "kw2"],
  "categoryMap": {
    "<topic>": ["<category>", ...],
    "*": ["<default category>", ...]
  }
}
```

| Field         | Purpose                                                                                                                                          |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------|
| `blacklist`   | Path to the blacklist JSON (URLs to drop from results, with reasons). Relative to `config.json`.                                                 |
| `includes`    | Path to the includes JSON (manual entries and GitHub repos to fetch by full name). Relative to `config.json`.                                    |
| `output`      | Path to the generated tools listing. Written by `update` on every run, read by `review` to find new tools. Relative to `config.json`.            |
| `keywords`    | GitHub topics to search for (OR-joined, `in:topic`).                                                                                             |
| `categoryMap` | Maps repo topics to tool categories. The special `"*"` key provides the default categories used when no topic matches or the repo has no topics. |

Each repo gets a `category` list derived from its GitHub topics via `categoryMap`, falling back to the `"*"` default.
