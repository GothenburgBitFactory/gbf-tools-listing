#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.10"
# dependencies = ["PyGithub >= 2.9"]
# ///

from datetime import datetime, timezone
import json
import os
import sys
import time
from enum import IntEnum
from github import Github, Auth, GithubException
from json import JSONDecodeError


class LogLevel(IntEnum):
    TRACE = 0
    DEBUG = 1
    INFO = 2
    WARN = 3
    ERROR = 4


# Categories derived from repo topics, loaded from the config file's
# `categoryMap`. The `"*"` entry (if present) provides the default categories
# used when a repo's topics match no other entry.
CATEGORIES = {}
DEFAULT_CATEGORIES = []

# The number of days at which point we consider a repository dormant (3 years)
DAYS_DORMANT = 3 * 365

# Configuration loaded from the --config file. Populated in __main__ before
# any of the data-loading functions are used.
BLACKLIST_PATH = None
INCLUDE_PATH = None
TOPICS = []


def log_message(message, *args, label=None):
    if label is None:
        print(message.format(*args))
    else:
        print("[{}]".format(label), message.format(*args))


def log_trace(message, *args):
    if LOG_LEVEL > LogLevel.TRACE:
        return
    log_message(message, *args, label="TRACE")


def log_debug(message, *args):
    if LOG_LEVEL > LogLevel.DEBUG:
        return
    log_message(message, *args, label="DEBUG")


def log_info(message, *args):
    if LOG_LEVEL > LogLevel.INFO:
        return
    if LOG_LEVEL == LogLevel.INFO:
        log_message(message, *args)
    else:
        log_message(message, *args, label="INFO")


def log_warn(message, *args):
    if LOG_LEVEL > LogLevel.WARN:
        return
    log_message(message, *args, label="WARN")


def log_error(message, *args):
    if LOG_LEVEL > LogLevel.ERROR:
        return
    log_message(message, *args, label="ERROR")


def search_github(names, topics):
    """
    Search GitHub for repos where any of `topics` is set as a repository topic.
    """
    client = Github(auth=Auth.Token(GITHUB_API_KEY))

    results = []

    log_debug("Processing {} manual entries", len(names))
    for name in names:
        log_debug("Querying GitHub for repository '{}'", name)
        results.append(from_github_repo(client.get_repo(name)))

    total = len(results)
    log_info("Querying GitHub for repositories with '{}' as topic...", ' OR '.join(topics))
    repos = client.search_repositories(' OR '.join(topics), **{"in": "topic"})
    log_debug("Found {} repositories", repos.totalCount)
    total += repos.totalCount

    try:
        for repo in repos:
            if len(results) % 30 == 0:
                rate_limits = client.get_rate_limit()
                log_debug("Rate limits:\n- core: {}\n- search: {}", rate_limits.resources.core, rate_limits.resources.search)
                log_debug("Rate limits: {}", rate_limits.raw_data)
                calculate_sleep_search(rate_limits.resources)

            results.append(from_github_repo(repo))
            log_debug("Adding '{}' as {}/{}", repo.html_url, len(results), total)

            sleep_period = calculate_sleep_core(repo.raw_headers)

            log_debug("Sleeping {:.3f} s", sleep_period)
            time.sleep(sleep_period)
    except GithubException as e:
        log_error("Encountered exception {} with headers {}", e, e.headers)
        raise e

    log_info("Received {} entries from GitHub", len(results))

    return results


def from_github_repo(repo):
    """
    Convert repo object from GitHub v3 API to our own format

    archived:    flag indicating whether the tool repository has been archived
    categories:  list of tool categories
    description: description of the tool
    dormant:     flag indicating whether the tool is deemed dormant or not
    language:    language the tool is written in
    license:     license the tool is released under
    name:        name of the tool
    owner:       owner of the tool's repository
    rating:      rating of the tool
    updated:     date the tool was last updated
    url:         url of the tool's repository
    """
    data = {
        "archived": repo.archived,
        "category": sorted(filter_categories(repo.topics)),
        "description": repo.description,
        "dormant": is_dormant(repo.pushed_at),
        "language": [repo.language if repo.language is not None else "N/A"],
        # Oddly the `license` isn't exposed by the library and would normally require an additional request.
        "license": repo._rawData["license"]["name"] if repo._rawData["license"] else None,
        "name": repo.name,
        "owner": [repo.owner.login],
        "rating": repo.stargazers_count,
        "updated": repo.pushed_at.date(),
        "url": repo.html_url,
    }

    return data


def filter_categories(topics):
    if topics:
        categories = set()
        log_debug("Found topics {}", topics)
        for topic in topics:
            if topic in CATEGORIES.keys():
                categories.update(CATEGORIES[topic])
        if len(categories) == 0:
            log_debug("No categories found, defaulting to {}", DEFAULT_CATEGORIES)
            return DEFAULT_CATEGORIES
        else:
            log_debug("Mapped to {}", list(categories))
            return list(categories)
    else:
        log_debug("No topics found, defaulting to {}", DEFAULT_CATEGORIES)
        return DEFAULT_CATEGORIES


def is_dormant(pushed_at):
    """
    A repo is considered dormant after 3 years of inactivity
    """
    elapsed = datetime.now(timezone.utc) - pushed_at
    return elapsed.days > DAYS_DORMANT


def calculate_sleep_core(headers):
    resource_name = headers['x-ratelimit-resource'].capitalize()
    remaining_requests = int(headers['x-ratelimit-remaining'])
    max_requests = headers['x-ratelimit-limit']
    reset_time = float(headers['x-ratelimit-reset'])

    log_trace("{} rate limit: {} of {} requests remaining",
              resource_name,
              remaining_requests,
              max_requests)

    current_time = time.time()
    log_trace("Now is {}", current_time)
    diff = reset_time - current_time if reset_time > current_time else 0
    log_trace("{}: {:.3f} s until rate limit reset ({})", resource_name, diff, reset_time)
    sleep_period = diff / remaining_requests if remaining_requests > 0 else diff + 5
    log_trace("{}: sleep {}", resource_name, sleep_period)

    return sleep_period


def calculate_sleep_search(limits):
    resource_name = "Search"
    remaining_requests = limits.search.remaining
    max_requests = limits.search.limit
    reset_time = limits.search.reset.timestamp()

    log_trace("{} rate limit: {} of {} requests remaining",
              resource_name,
              remaining_requests,
              max_requests)

    current_time = time.time()
    log_trace("Now is {}", current_time)
    diff = reset_time - current_time if reset_time > current_time else 0
    log_trace("{}: {:.3f} s until rate limit reset ({})", resource_name, diff, reset_time)
    sleep_period = diff / remaining_requests if remaining_requests > 0 else diff + 5
    log_trace("{}: sleep {}", resource_name, sleep_period)

    return sleep_period


def filter_tools(inputs):
    """
    Removes duplicates and blacklisted entries based on the url
    """
    results = []
    blacklist = load_file(BLACKLIST_PATH)
    seen = set()

    for tool in inputs:
        url = tool["url"]

        if url in seen:
            log_debug("Dropping '{}' because it is a duplicate", url)
            continue
        elif url in blacklist:
            log_debug("Dropping '{}' because it {}", url, blacklist[url])
            continue

        log_debug("Keeping '{}'", url)
        seen.add(url)
        results.append(tool)

    return results


def load_file(filepath):
    try:
        with open(filepath) as f:
            return json.load(f)
    except FileNotFoundError:
        log_info("File '{}' not found!", filepath)
        return dict()
    except JSONDecodeError:
        log_warn("Could not parse file '{}'!", filepath)
        return dict()


def load_config(config_path):
    """
    Load the config file and populate the module-level configuration globals
    (BLACKLIST_PATH, INCLUDE_PATH, TOPICS, CATEGORIES, DEFAULT_CATEGORIES).

    Relative paths in the config are resolved with respect to the directory
    containing the config file.
    """
    config = load_file(config_path)
    if not config:
        log_error("Config file at '{}' is missing or empty", config_path)
        exit(1)

    required = ("blacklist", "includes", "keywords", "categoryMap")
    missing = [k for k in required if k not in config]
    if missing:
        log_error("Config at '{}' is missing keys: {}", config_path, ", ".join(missing))
        exit(1)

    config_dir = os.path.dirname(os.path.realpath(config_path))

    global BLACKLIST_PATH, INCLUDE_PATH, TOPICS, CATEGORIES, DEFAULT_CATEGORIES

    BLACKLIST_PATH = os.path.join(config_dir, config["blacklist"])
    INCLUDE_PATH = os.path.join(config_dir, config["includes"])
    TOPICS = list(config["keywords"])

    category_map = config["categoryMap"]
    CATEGORIES.clear()
    for topic, categories in category_map.items():
        if topic == "*":
            continue
        CATEGORIES[topic] = list(categories)
    DEFAULT_CATEGORIES.extend(category_map.get("*", []))

    log_debug("Config loaded from '{}'", config_path)
    log_debug("  blacklist:   {}", BLACKLIST_PATH)
    log_debug("  includes:    {}", INCLUDE_PATH)
    log_debug("  keywords:    {}", TOPICS)
    log_debug("  categoryMap: {} entries, default: {}", len(CATEGORIES), DEFAULT_CATEGORIES)


def usage():
    return ("USAGE: %s --config <path/to/config.json> [output_file]\n\n"
            "  --config <path>  - required, path to the config JSON file\n"
            "  output_file      - optional, defaults to stdout\n") % sys.argv[0]


if __name__ == "__main__":
    LOG_LEVEL = LogLevel[os.getenv("LOG_LEVEL") or "INFO"]
    log_debug("Log level set to '{}'", str(LOG_LEVEL.name))

    GITHUB_API_KEY = os.getenv("GITHUB_API_KEY")
    if not GITHUB_API_KEY:
        log_error("The environment variable GITHUB_API_KEY is not set!")
        exit(1)

    config_path = None
    output = None

    args = sys.argv[1:]
    while args:
        arg = args.pop(0)
        if arg == "--config":
            if not args:
                log_error("--config requires a value")
                print(usage())
                exit(1)
            config_path = args.pop(0)
        elif arg in ("-h", "--help"):
            print(usage())
            exit(0)
        elif output is None:
            output = arg
        else:
            log_error("Unexpected argument: {}", arg)
            print(usage())
            exit(1)

    if not config_path:
        log_error("--config is required")
        print(usage())
        exit(1)

    load_config(config_path)

    if output:
        log_debug("Will write output to {}", output)
        output = open(output, mode="w")
    else:
        log_debug("Will write output to stdout")
        output = sys.stdout

    includes = load_file(INCLUDE_PATH)
    includes["github"] = [] if "github" not in includes else includes["github"]
    includes["manual"] = [] if "manual" not in includes else includes["manual"]

    log_info("Updating tool listing...")
    log_info("Querying GitHub...")
    tools = search_github(includes["github"], TOPICS)
    log_info("Adding {} manual includes ...", len(includes["manual"]))
    tools.extend(includes["manual"])
    log_info("Filtering {} tools ...", len(tools))
    tools = filter_tools(tools)
    log_debug("Sorting tools...")
    tools.sort(key=lambda x: x.get("url") if x.get("url") is not None else "")
    log_info("Writing {} tools to {} ...", len(tools), output.name)
    json.dump(tools, output, indent=2, sort_keys=True, default=str)
    log_info("Update complete.")
