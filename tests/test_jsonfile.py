"""Tests for the shared JSON file reader."""

import json

import pytest

from tools_list.jsonfile import read_json


def test_read_json(tmp_path):
    path = tmp_path / "data.json"
    path.write_text('{"a": 1}')
    assert read_json(path) == {"a": 1}


def test_read_json_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_json(tmp_path / "nope.json")


def test_read_json_invalid_json(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{invalid")
    with pytest.raises(json.JSONDecodeError):
        read_json(path)
