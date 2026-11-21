"""Reading JSON data files."""

import json


def read_json(path):
    """Read a JSON file; raises FileNotFoundError or json.JSONDecodeError."""
    with open(path, encoding="utf-8") as file:
        return json.load(file)
