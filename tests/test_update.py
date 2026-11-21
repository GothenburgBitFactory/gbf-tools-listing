"""Tests for the update command, comparing its output against a committed fixture."""

import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools_list import sources
from tools_list.cli import main
from tools_list.commands.update import load_data

FIXTURE = Path(__file__).parent / "fixtures" / "expected-tools-data.json"

FROZEN_NOW = datetime(2026, 10, 24, 12, 0, tzinfo=timezone.utc)


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        return FROZEN_NOW


class FakeAuth:
    class Token:
        def __init__(self, token):
            self.token = token


class FakeGithubException(Exception):
    def __init__(self, *args):
        super().__init__(*args)
        self.headers = {}


class FakeRepo:
    def __init__(self, full_name, description, topics, language, pushed_at, stars, archived, license_name):
        self.name = full_name.split("/")[-1]
        self.html_url = "https://github.com/" + full_name
        self.description = description
        self.topics = topics
        self.language = language
        self.pushed_at = pushed_at
        self.stargazers_count = stars
        self.archived = archived
        self._rawData = {"license": {"name": license_name} if license_name else None}
        self.owner = types.SimpleNamespace(login=full_name.split("/")[0])
        self.raw_headers = {
            "x-ratelimit-resource": "search",
            "x-ratelimit-remaining": "5000",
            "x-ratelimit-limit": "5000",
            "x-ratelimit-reset": "0",
        }


NAMED_REPOS = {
    "owner/good": FakeRepo(
        "owner/good",
        "A good tool",
        ["taskwarrior"],
        "Python",
        datetime(2026, 1, 1, tzinfo=timezone.utc),
        10,
        False,
        "MIT",
    ),
    "owner/dead": FakeRepo(
        "owner/dead", "A dead tool", [], "Shell", datetime(2026, 2, 2, tzinfo=timezone.utc), 1, False, None
    ),
}

SEARCH_REPOS = [
    NAMED_REPOS["owner/good"],
    FakeRepo(
        "owner/searched",
        "A dormant tool",
        ["taskwarrior", "extra"],
        None,
        datetime(2020, 3, 3, tzinfo=timezone.utc),
        42,
        True,
        None,
    ),
    FakeRepo(
        "owner/blacklisted-search",
        "A blacklisted tool",
        ["taskwarrior"],
        "Rust",
        datetime(2026, 4, 4, tzinfo=timezone.utc),
        5,
        False,
        "MIT",
    ),
]


class FakeSearchResults:
    totalCount = len(SEARCH_REPOS)

    def __iter__(self):
        return iter(SEARCH_REPOS)


class FakeRateLimits:
    def __init__(self):
        self.resources = types.SimpleNamespace(
            core="core",
            search=types.SimpleNamespace(remaining=30, limit=30, reset=datetime(2020, 1, 1, tzinfo=timezone.utc)),
        )
        self.raw_data = {}


class FakeGithub:
    def __init__(self, auth=None):
        self.auth = auth

    def get_repo(self, name):
        return NAMED_REPOS[name]

    def search_repositories(self, query, **kwargs):
        return FakeSearchResults()

    def get_rate_limit(self):
        return FakeRateLimits()


def build_fake_github():
    fake = types.ModuleType("github")
    fake.Auth = FakeAuth
    fake.Github = FakeGithub
    fake.GithubException = FakeGithubException
    return fake


def make_project(directory):
    """Create a scratch project with config, blacklist and includes."""
    directory = Path(directory)
    directory.mkdir(parents=True)
    (directory / "config.json").write_text(
        json.dumps(
            {
                "blacklist": "blacklist.json",
                "includes": "include.json",
                "output": "tools-data.json",
                "keywords": ["taskwarrior"],
                "categoryMap": {"taskwarrior": ["taskwarrior3"], "*": ["taskwarrior2"]},
            }
        )
    )
    (directory / "blacklist.json").write_text(
        json.dumps(
            {
                "https://github.com/owner/dead": "is broken",
                "https://github.com/owner/blacklisted-search": "is unrelated",
                "https://github.com/owner/manual-blacklisted": "is spam",
            }
        )
    )
    (directory / "include.json").write_text(
        json.dumps(
            {
                "github": ["owner/good", "owner/dead"],
                "manual": [
                    {"name": "Manual Tool", "url": None, "description": "A tool without repository"},
                    {
                        "name": "Manual Blacklisted",
                        "url": "https://github.com/owner/manual-blacklisted",
                        "description": "Dropped by the blacklist",
                    },
                ],
            }
        )
    )
    return directory


def install_fake(monkeypatch):
    monkeypatch.setitem(sys.modules, "github", build_fake_github())
    monkeypatch.setattr(sources.github, "datetime", FrozenDatetime)
    monkeypatch.setenv("GITHUB_API_KEY", "dummy")


def test_update_requires_github_api_key(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("GITHUB_API_KEY", raising=False)
    project = make_project(tmp_path / "project")
    with pytest.raises(SystemExit) as excinfo:
        main(["update", str(project)])
    assert excinfo.value.code == 1
    assert "GITHUB_API_KEY is not set" in capsys.readouterr().out


def test_update_golden_output(monkeypatch, capsys, tmp_path):
    install_fake(monkeypatch)
    project = make_project(tmp_path / "project")

    main(["update", str(project)])

    assert (project / "tools-data.json").read_bytes() == FIXTURE.read_bytes()


def test_update_subdirectory_output(monkeypatch, capsys, tmp_path):
    install_fake(monkeypatch)
    project = make_project(tmp_path / "project")
    (project / "data").mkdir()
    config = json.loads((project / "config.json").read_text())
    config["output"] = "data/tools-data.json"
    (project / "config.json").write_text(json.dumps(config))

    main(["update", str(project)])

    assert (project / "data" / "tools-data.json").read_bytes() == FIXTURE.read_bytes()


def test_load_data_not_found(tmp_path, capsys):
    assert load_data(tmp_path / "nope.json") == {}
    assert "not found!" in capsys.readouterr().out


def test_load_data_invalid_json(tmp_path, capsys):
    path = tmp_path / "broken.json"
    path.write_text("{invalid")
    assert load_data(path) == {}
    assert "Could not parse" in capsys.readouterr().out
