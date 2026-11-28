"""Loading and validation of the per-project config.json."""

import json
from dataclasses import dataclass
from pathlib import Path

from tools_list.jsonfile import read_json
from tools_list.log import die, log_debug

CONFIG_FILE = "config.json"

REQUIRED_KEYS = ("blacklist", "includes", "output", "keywords", "categoryMap")


@dataclass
class ProjectConfig:
    """Everything the sources and commands need to know about a project."""

    directory: Path
    config_path: Path
    blacklist_path: Path
    includes_path: Path
    output_path: Path
    keywords: list
    categories: dict
    default_categories: list


def load_config(project):
    """
    Load and validate the project directory and its config.json.

    The project must be an existing directory containing a config.json;
    relative paths in the config are resolved with respect to that directory.
    """
    project = Path(project)
    if not project.is_dir():
        die(f"'{project}' is not a directory!")

    config_path = project / CONFIG_FILE
    try:
        config = read_json(config_path)
    except FileNotFoundError:
        die(f"Missing '{config_path}'!")
    except json.JSONDecodeError as error:
        die(f"'{config_path}' is not valid JSON: {error}")
    if not config:
        die("Config file at '{}' is missing or empty", config_path)

    missing = [key for key in REQUIRED_KEYS if key not in config]
    if missing:
        die("Config at '{}' is missing keys: {}", config_path, ", ".join(missing))

    directory = config_path.resolve().parent
    project_config = ProjectConfig(
        directory=directory,
        config_path=config_path,
        blacklist_path=directory / config["blacklist"],
        includes_path=directory / config["includes"],
        output_path=directory / config["output"],
        keywords=list(config["keywords"]),
        categories={topic: list(categories) for topic, categories in config["categoryMap"].items() if topic != "*"},
        default_categories=list(config["categoryMap"].get("*", [])),
    )

    log_debug("Config loaded from '{}'", config_path)
    log_debug("  blacklist:   {}", project_config.blacklist_path)
    log_debug("  includes:    {}", project_config.includes_path)
    log_debug("  output:      {}", project_config.output_path)
    log_debug("  keywords:    {}", project_config.keywords)
    log_debug(
        "  categoryMap: {} entries, default: {}", len(project_config.categories), project_config.default_categories
    )

    return project_config
