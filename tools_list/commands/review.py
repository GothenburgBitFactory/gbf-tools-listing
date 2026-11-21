"""The review command: interactively review the blacklist and new tools."""

import re
import shutil
import subprocess
import webbrowser
from datetime import datetime

from tools_list.blacklist import check_blacklist_entry, display_path, load_blacklist, write_blacklist
from tools_list.config import load_config
from tools_list.log import clear_progress, die, log_info, show_progress

TIMESTAMP_FILE = ".review-timestamp"

DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
SHA_PATTERN = re.compile(r"[0-9a-fA-F]{7,40}")
# Added '"url": "..."' lines in diffs of tools-data.json ('"url": null' never matches).
ADDED_URL_PATTERN = re.compile(r'^\+\s+"url": "(.*)"')


def run_git(directory, *args, check=True):
    result = subprocess.run(["git", *args], cwd=directory, capture_output=True, text=True)
    if check and result.returncode != 0:
        die(f"git {' '.join(args)} failed!\n{result.stderr.strip()}")
    return result


def ask(question, choices, default):
    """Ask `question` until one of `choices` is given; empty input picks `default`."""
    hint = "/".join(choice.upper() if choice == default else choice for choice in choices)
    while True:
        answer = input(f"{question} ({hint}): ").strip().lower()
        if not answer:
            return default
        if answer in choices:
            return answer
        print(f"Please answer one of: {', '.join(choices)}.")


def ask_yes_no(question, default):
    return ask(question, ("y", "n"), default) == "y"


def open_in_browser(url):
    if webbrowser.open(url):
        return
    die(f"Could not open '{url}' in a browser!")


def review_blacklist(blacklist):
    log_info(f"Reviewing {len(blacklist)} entries...")
    urls = sorted(blacklist)
    for index, url in enumerate(urls, 1):
        show_progress(index, len(urls), url)
        new_url = check_blacklist_entry(url)
        clear_progress()
        if new_url is None:
            del blacklist[url]
            log_info(f"Repository '{url}' does no longer exist, purging...")
            continue
        if new_url != url:
            blacklist[new_url] = blacklist.pop(url)
            log_info(f"Repository '{url}' was renamed to '{new_url}', updating...")
        url = new_url
        open_in_browser(url)
        log_info(f"{url} was blacklisted because it '{blacklist[url]}'")
        choice = ask(f"Keep {url} in blacklist?", ("y", "n", "u"), "y")
        if choice == "n":
            del blacklist[url]
        elif choice == "u":
            blacklist[url] = input("Update reason: because it ... ").strip()


def find_added_urls(directory, tools_data_file, base):
    """The tool URLs added to tools-data.json since the base commit (None = since the beginning).

    A combined diff between the base commit and HEAD, so tools that were removed
    and re-added in between do not count as additions. Diffing against the empty
    tree shows the whole current file as added.
    """
    if not base:
        base = run_git(directory, "hash-object", "-t", "tree", "/dev/null").stdout.strip()
    diff = run_git(directory, "diff", base, "HEAD", "--", str(tools_data_file)).stdout
    urls = set()
    for line in diff.split("\n"):
        match = ADDED_URL_PATTERN.match(line)
        if match and match.group(1):
            urls.add(match.group(1))
    return sorted(urls)


def resolve_base_commit(directory, marker):
    """The commit tools-data.json is compared against: a --since or last-review marker (None = everything)."""
    if not marker:
        return None
    commit, kind = marker
    return commit if kind == "sha" else last_commit_before(directory, commit)


def display_marker(directory, marker):
    """The marker as shown to the user: the date, or the commit's short sha."""
    commit, kind = marker
    return commit if kind == "date" else run_git(directory, "rev-parse", "--short", commit).stdout.strip()


def last_commit_before(directory, date):
    """The newest commit committed before the start of `date`."""
    return run_git(directory, "rev-list", "-1", f"--until={date}", "HEAD").stdout.strip()


def review_new_tools(urls):
    """Review the new tools, asking for each whether to blacklist it; return the additions."""
    additions = {}
    for url in urls:
        open_in_browser(url)
        if ask_yes_no(f"Blacklist {url}?", "n"):
            additions[url] = input("Specify reason: because it ... ").strip()
    return additions


def validate_since(value, directory):
    """Return a (date-or-short-sha, kind) pair for a --since value."""
    if DATE_PATTERN.fullmatch(value):
        try:
            datetime.strptime(value, "%Y-%m-%d")
        except ValueError:
            die(f"'{value}' is not a valid date (expected YYYY-MM-DD)!")
        return value, "date"
    if SHA_PATTERN.fullmatch(value):
        if run_git(directory, "rev-parse", "--verify", "--quiet", f"{value}^{{commit}}", check=False).returncode != 0:
            die(f"'{value}' is not a commit in this repository!")
        if run_git(directory, "merge-base", "--is-ancestor", value, "HEAD", check=False).returncode != 0:
            die(f"Commit '{value}' is not an ancestor of HEAD!")
        return run_git(directory, "rev-parse", "--short", f"{value}^{{commit}}").stdout.strip(), "sha"
    die(f"Invalid --since value '{value}' (expected YYYY-MM-DD date or commit SHA)!")


def read_review_marker(timestamp_file):
    """The (commit, kind) of the last review; kind is 'sha', or 'date' for legacy files with only a date."""
    if not timestamp_file.exists():
        return None
    lines = timestamp_file.read_text().split()
    if lines and SHA_PATTERN.fullmatch(lines[0]):
        return lines[0], "sha"
    if len(lines) == 1 and DATE_PATTERN.fullmatch(lines[0]):
        return lines[0], "date"
    die(f"'{timestamp_file}' does not contain a review commit SHA or date!")


def update_review_marker(directory, timestamp_file, tools_data_file):
    """Record the last commit that changed tools-data.json, so the next review only sees newer additions.

    If the file was never committed there is no such commit yet and nothing is recorded,
    so the whole listing is up for review once it is.
    """
    sha = run_git(directory, "log", "-1", "--format=%H", "--", str(tools_data_file)).stdout.strip()
    if sha:
        timestamp_file.write_text(f"{sha}\n")


def blacklist_unchanged(app_dir, blacklist_file) -> bool:
    return run_git(app_dir, "diff", "--quiet", str(blacklist_file), check=False).returncode == 0


def commit_changes(app_dir, blacklist_file, message):
    run_git(app_dir, "add", str(blacklist_file))
    run_git(app_dir, "commit", "-m", message)


def run(args):
    if not shutil.which("git"):
        die("Required tool 'git' is either inaccessible or not installed!")

    config = load_config(args.project)
    app_dir = config.directory
    since = validate_since(args.since, app_dir) if args.since else None
    blacklist_file = config.blacklist_path
    tools_data_file = config.output_path
    timestamp_file = app_dir / TIMESTAMP_FILE

    if not tools_data_file.exists():
        die(f"Missing '{tools_data_file}'!")

    blacklist = load_blacklist(blacklist_file)

    if not blacklist:
        log_info("Current blacklist is empty!")
    elif ask_yes_no(f"Review current blacklist ({len(blacklist)} items)?", "n"):
        review_blacklist(blacklist)

    marker = since or read_review_marker(timestamp_file)
    base = resolve_base_commit(app_dir, marker)
    urls = find_added_urls(app_dir, tools_data_file, base)
    added_since = f", added since {display_marker(app_dir, marker)}" if marker else ""

    if not urls:
        log_info("No new tools found to review!")
        update_review_marker(app_dir, timestamp_file, tools_data_file)
    elif ask_yes_no(f"Review {len(urls)} new tools{added_since}?", "y"):
        log_info(f"Reviewing {len(urls)} tools{added_since}...")
        blacklist.update(review_new_tools(urls))
        update_review_marker(app_dir, timestamp_file, tools_data_file)

    display = display_path(app_dir, blacklist_file)
    log_info(f"Writing {len(blacklist)} entries to '{display}'...")
    write_blacklist(blacklist_file, blacklist)

    if blacklist_unchanged(app_dir, blacklist_file):
        log_info(f"No changes to {display}, nothing to commit!")
        return
    elif ask_yes_no(f"Commit changes to {display}?", "y"):
        message = f"Update {display}"
        commit_changes(app_dir, blacklist_file, message)
