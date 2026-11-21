"""Tests for config.json loading and validation."""

import json

import pytest

from tools_list.config import load_config


def make_project(tmp_path, config):
    directory = tmp_path / "project"
    directory.mkdir()
    if config is not None:
        (directory / "config.json").write_text(json.dumps(config))
    return directory


def valid_config():
    return {
        "blacklist": "blacklist.json",
        "includes": "include.json",
        "output": "tools-data.json",
        "keywords": ["taskwarrior"],
        "categoryMap": {"taskwarrior": ["taskwarrior3"], "*": ["taskwarrior2"]},
    }


def test_load_config_resolves_paths(tmp_path):
    project = make_project(tmp_path, valid_config())
    config = load_config(project)
    assert config.directory == (project / "config.json").resolve().parent
    assert config.blacklist_path == config.directory / "blacklist.json"
    assert config.includes_path == config.directory / "include.json"
    assert config.output_path == config.directory / "tools-data.json"
    assert config.keywords == ["taskwarrior"]
    assert config.categories == {"taskwarrior": ["taskwarrior3"]}
    assert config.default_categories == ["taskwarrior2"]


def test_load_config_missing_file(tmp_path, capsys):
    project = make_project(tmp_path, None)
    with pytest.raises(SystemExit) as excinfo:
        load_config(project)
    assert excinfo.value.code == 1
    assert "Missing '" in capsys.readouterr().out


def test_load_config_empty_file(tmp_path, capsys):
    project = make_project(tmp_path, {})
    with pytest.raises(SystemExit) as excinfo:
        load_config(project)
    assert excinfo.value.code == 1
    assert "missing or empty" in capsys.readouterr().out


def test_load_config_invalid_json(tmp_path, capsys):
    project = tmp_path / "project"
    project.mkdir()
    (project / "config.json").write_text("{invalid")
    with pytest.raises(SystemExit) as excinfo:
        load_config(project)
    assert excinfo.value.code == 1
    assert "is not valid JSON" in capsys.readouterr().out


def test_load_config_missing_keys(tmp_path, capsys):
    config = valid_config()
    del config["output"]
    del config["keywords"]
    project = make_project(tmp_path, config)
    with pytest.raises(SystemExit) as excinfo:
        load_config(project)
    assert excinfo.value.code == 1
    assert "missing keys: output, keywords" in capsys.readouterr().out
