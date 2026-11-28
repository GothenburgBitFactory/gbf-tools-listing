"""GitHub source: includes by full repository name and search by topic."""

import os
import time
from datetime import datetime, timezone

from tools_list.log import die, log_debug, log_error, log_info, log_trace
from tools_list.sources.base import filter_tools

DAYS_DORMANT = 3 * 365


class GithubSource:
    name = "github"

    def collect(self, config, blacklist, includes):
        api_key = os.environ.get("GITHUB_API_KEY")
        if not api_key:
            die("The environment variable GITHUB_API_KEY is not set!")

        from github import Auth, Github, GithubException

        log_info("Querying GitHub...")
        client = Github(auth=Auth.Token(os.environ["GITHUB_API_KEY"]))

        results = []

        names = includes.get("github", [])
        log_debug("Processing {} manual entries", len(names))
        for name in names:
            log_debug("Querying GitHub for repository '{}'", name)
            results.append(from_github_repo(client.get_repo(name), config))

        topics = config.keywords
        total = len(results)
        log_info("Querying GitHub for repositories with '{}' as topic...", " OR ".join(topics))
        repos = client.search_repositories(" OR ".join(topics), **{"in": "topic"})
        log_debug("Found {} repositories", repos.totalCount)
        total += repos.totalCount

        try:
            for repo in repos:
                if len(results) % 30 == 0:
                    rate_limits = client.get_rate_limit()
                    log_debug(
                        "Rate limits:\n- core: {}\n- search: {}",
                        rate_limits.resources.core,
                        rate_limits.resources.search,
                    )
                    log_debug("Rate limits: {}", rate_limits.raw_data)
                    calculate_sleep_search(rate_limits.resources)

                results.append(from_github_repo(repo, config))
                log_debug("Adding '{}' as {}/{}", repo.html_url, len(results), total)

                sleep_period = calculate_sleep_core(repo.raw_headers)

                log_debug("Sleeping {:.3f} s", sleep_period)
                time.sleep(sleep_period)
        except GithubException as e:
            log_error("Encountered exception {} with headers {}", e, e.headers)
            raise e

        log_info("Received {} entries from GitHub", len(results))

        return filter_tools(results, blacklist)


def from_github_repo(repo, config):
    """
    Convert repo object from GitHub v3 API to our own format

    archived:    flag indicating whether the tool repository has been archived
    category:    list of tool categories
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
        "category": sorted(filter_categories(repo.topics, config)),
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


def filter_categories(topics, config):
    if topics:
        categories = set()
        log_debug("Found topics {}", topics)
        for topic in topics:
            if topic in config.categories:
                categories.update(config.categories[topic])
        if len(categories) == 0:
            log_debug("No categories found, defaulting to {}", config.default_categories)
            return config.default_categories
        else:
            log_debug("Mapped to {}", list(categories))
            return list(categories)
    else:
        log_debug("No topics found, defaulting to {}", config.default_categories)
        return config.default_categories


def is_dormant(pushed_at):
    """
    A repo is considered dormant after 3 years of inactivity
    """
    elapsed = datetime.now(timezone.utc) - pushed_at
    return elapsed.days > DAYS_DORMANT


def calculate_sleep_core(headers):
    resource_name = headers["x-ratelimit-resource"].capitalize()
    remaining_requests = int(headers["x-ratelimit-remaining"])
    max_requests = headers["x-ratelimit-limit"]
    reset_time = float(headers["x-ratelimit-reset"])

    log_trace("{} rate limit: {} of {} requests remaining", resource_name, remaining_requests, max_requests)

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

    log_trace("{} rate limit: {} of {} requests remaining", resource_name, remaining_requests, max_requests)

    current_time = time.time()
    log_trace("Now is {}", current_time)
    diff = reset_time - current_time if reset_time > current_time else 0
    log_trace("{}: {:.3f} s until rate limit reset ({})", resource_name, diff, reset_time)
    sleep_period = diff / remaining_requests if remaining_requests > 0 else diff + 5
    log_trace("{}: sleep {}", resource_name, sleep_period)

    return sleep_period
