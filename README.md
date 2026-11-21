# GBF Tools Listing

Home of the data files for the tools pages of
* [taskwarrior.org](https://taskwarrior.org/tools/)
* [timewarrior.net](https://timewarrior.net/tools/)

CI regenerates the listings regularly (see `.github/workflows/`) using the `tools-list` CLI tool.
This tool is also used for manual maintenance to keep the tools listing focused.
See the documentation links at the bottom for more details.

## Repository layout

There is one directory per project, plus the `tools_list` package:

```
task/           # Taskwarrior
timew/          # Timewarrior
tools_list/     # the tools-list package
tests/
```

Each project directory holds:

| File                | Committed | Purpose                                                    |
|---------------------|-----------|------------------------------------------------------------|
| `config.json`       | yes       | all project-specific inputs for the tool                   |
| `include.json`      | yes       | manual URL entries for tools the topic search cannot find  |
| `blacklist.json`    | yes       | URLs to drop from the listing, with reasons                |
| `tools-data.json`   | yes       | the generated listing                                      |
| `.review-timestamp` | no        | last reviewed commit of `tools-data.json`, local file only |

Blacklist changes are usually made by running `tools-list review` (see [Review a tools listing](docs/review.md)).
Manual includes are rather the exception, see [Manually update a tools listing](docs/update.md) on how they work.

The tool has no built-in notion of any specific project: everything project-specific is supplied via the project's `config.json`, so adding a new project is just a new directory plus a workflow.

## Documentation

* [Update a tools listing](docs/update.md)
* [Review a tools listing](docs/review.md)
* [CLI and config reference](docs/reference.md)
