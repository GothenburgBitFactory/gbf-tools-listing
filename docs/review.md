# Review a tools listing

How to review the changes CI landed in a tools listing, and maintain the project blacklist.
The CI updates land in the listings unreviewed — `tools-list review` is the interactive counterpart that reviews them.
No GitHub API token is required:

```bash
$ uv run tools-list review <project>
```

The blacklist (`blacklist` field) and the listing (`output` field) are read from the project's `config.json`.

## During a review

A run works through two queues:

1. The current blacklist (optional, default: skip) — each entry is opened in the browser, its reason is shown, and you decide to keep it, remove it, or update its reason.
2. New tools — every URL added to the listing since the last review.
   Each tool is opened in the browser and you decide whether to blacklist it (with a reason).

Which tools count as new: the last commit of the listing that has been reviewed is recorded in the project's `.review-timestamp`, a local file that is not committed.
Additions are determined via a combined diff against that commit, so tools that were removed and re-added in between do not count as new.
If the file does not exist yet, all entries in the listing are listed.

While the blacklist is processed, every entry's URL is checked first:
URLs returning a 404 remove the entry automatically, and repositories that were renamed are updated to their new URL.
Any other error aborts the run.

At all prompts, pressing return accepts the default.

## After a review

The blacklist is written back and you are asked whether to commit the changes.
After a completed review, `.review-timestamp` is updated to the last commit that changed the listing.

## Review a specific range

Use `--since` to review tools added since a given date (`YYYY-MM-DD`) or commit (an ancestor of `HEAD`) instead of since the recorded review commit:

```bash
$ uv run tools-list review --since 2025-11-01 <project>
```
