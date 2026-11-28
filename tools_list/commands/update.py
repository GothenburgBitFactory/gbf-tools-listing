"""The update command: regenerate the tools listing from all sources."""

import json

from tools_list.config import load_config
from tools_list.jsonfile import read_json
from tools_list.log import LOG_LEVEL, log_debug, log_info, log_warn
from tools_list.sources import SOURCES


def load_data(path):
    """Load a JSON data file, defaulting to empty if it is missing or invalid."""
    try:
        return read_json(path)
    except FileNotFoundError:
        log_info("File '{}' not found!", path)
    except json.JSONDecodeError:
        log_warn("Could not parse file '{}'!", path)
    return {}


def run(args):
    log_debug("Log level set to '{}'", str(LOG_LEVEL.name))

    config = load_config(args.project)
    log_debug("Will write output to {}", config.output_path)

    blacklist = load_data(config.blacklist_path)
    includes = load_data(config.includes_path)

    log_info("Updating tool listing...")

    tools = []
    for source in SOURCES:
        tools.extend(source.collect(config, blacklist, includes))

    log_debug("Sorting tools...")
    tools.sort(key=lambda tool: tool.get("url") if tool.get("url") is not None else "")
    log_info("Writing {} tools to {} ...", len(tools), config.output_path)
    with open(config.output_path, "w") as output:
        json.dump(tools, output, indent=2, sort_keys=True, default=str)
    log_info("Update complete.")
