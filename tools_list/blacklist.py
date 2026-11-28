"""Shared blacklist operations for the review and purge commands."""

import json
import urllib.error
import urllib.request

from tools_list.jsonfile import read_json
from tools_list.log import clear_progress, die


def load_blacklist(blacklist_file) -> dict:
    try:
        blacklist = read_json(blacklist_file)
        if not isinstance(blacklist, dict):
            die(f"'{blacklist_file}' does not contain a JSON object!")
        return blacklist

    except FileNotFoundError:
        die(f"Missing '{blacklist_file}'!")
    except json.JSONDecodeError as error:
        die(f"'{blacklist_file}' is not valid JSON: {error}")


def check_url(url):
    """Fetch the URL, following redirects; return (status, final URL). Dies on network errors."""
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            return response.status, response.geturl()
    except urllib.error.HTTPError as error:
        return error.code, error.geturl()
    except (urllib.error.URLError, OSError) as error:
        die(f"Request for '{url}' failed: {error}")


def check_blacklist_entry(url):
    """Check one blacklist URL; return the URL it should map to, or None if its repository is gone.

    A redirect returns the new URL; any status other than 200 and 404 aborts,
    after clearing the progress indicator so the error message stays readable.
    """
    status, final_url = check_url(url)
    if status == 200:
        return final_url
    if status == 404:
        return None
    clear_progress()
    die(f"Unhandled status code '{status}' for {url}!")


def display_path(app_dir, path):
    """The path as shown in output: the project directory and everything after it."""
    marker = f"/{app_dir.name}/"
    text = str(path)
    start = text.find(marker) + 1
    return text[start:] if start else text


def write_blacklist(blacklist_file, blacklist):
    with open(blacklist_file, "w", encoding="utf-8") as file:
        json.dump(blacklist, file, sort_keys=True, indent=4, ensure_ascii=False)
        file.write("\n")
