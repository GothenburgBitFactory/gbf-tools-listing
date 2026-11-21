"""Common interface and helpers for all tool sources."""

from typing import Protocol

from tools_list.log import log_debug, log_info


class Source(Protocol):
    """
    A provider of tools: queries an API, converts every item to the common
    tools data format, applies the blacklist and its part of the includes,
    and returns the final entries.
    """

    name: str

    def collect(self, config, blacklist, includes): ...


def filter_tools(inputs, blacklist):
    """
    Removes duplicates and blacklisted entries based on the URL.
    """
    log_info("Filtering {} tools ...", len(inputs))

    results = []
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
