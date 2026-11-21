"""Tests for the purge command."""

import json

import pytest

from tools_list import blacklist
from tools_list.cli import main


def write_json(path, data):
    path.write_text(json.dumps(data, sort_keys=True, indent=4, ensure_ascii=False) + "\n")


def make_project(tmp_path, blacklist):
    """A plain project directory - purge works without a git repository."""
    directory = tmp_path / "project"
    directory.mkdir()
    write_json(
        directory / "config.json",
        {
            "blacklist": "blacklist.json",
            "includes": "include.json",
            "output": "tools-data.json",
            "keywords": ["taskwarrior"],
            "categoryMap": {"*": ["default"]},
        },
    )
    write_json(directory / "blacklist.json", blacklist)
    return directory


def patch_check_url(monkeypatch, mapping):
    def fake_check_url(url):
        return mapping.get(url, (200, url))

    monkeypatch.setattr(blacklist, "check_url", fake_check_url)


def test_purge_removes_404_and_renames_urls(monkeypatch, capsys, tmp_path):
    project = make_project(
        tmp_path,
        {
            "https://x/gone": "is gone",
            "https://x/renamed": "is renamed",
            "https://x/stays": "is fine",
        },
    )
    patch_check_url(
        monkeypatch,
        {
            "https://x/gone": (404, "https://x/gone"),
            "https://x/renamed": (200, "https://x/newname"),
        },
    )

    main(["purge", str(project)])

    out = capsys.readouterr().out
    assert "purging..." in out
    assert "was renamed to 'https://x/newname'" in out
    assert "commit the changes when ready" in out
    blacklist = json.loads((project / "blacklist.json").read_text())
    assert blacklist == {"https://x/newname": "is renamed", "https://x/stays": "is fine"}


def test_purge_without_changes_writes_nothing(monkeypatch, capsys, tmp_path):
    blacklist = {"https://x/stays": "is fine"}
    project = make_project(tmp_path, blacklist)
    before = (project / "blacklist.json").read_bytes()
    patch_check_url(monkeypatch, {})

    main(["purge", str(project)])

    assert (project / "blacklist.json").read_bytes() == before
    assert "No changes to" in capsys.readouterr().out


def test_purge_aborts_on_unhandled_status(monkeypatch, capsys, tmp_path):
    project = make_project(tmp_path, {"https://x/err": "is broken"})
    patch_check_url(monkeypatch, {"https://x/err": (500, "https://x/err")})

    with pytest.raises(SystemExit) as excinfo:
        main(["purge", str(project)])
    assert excinfo.value.code == 1
    assert "Unhandled status code '500'" in capsys.readouterr().out


def test_purge_empty_blacklist(monkeypatch, capsys, tmp_path):
    project = make_project(tmp_path, {})
    patch_check_url(monkeypatch, {})

    main(["purge", str(project)])

    assert "Current blacklist is empty!" in capsys.readouterr().out


def test_purge_missing_directory(monkeypatch, capsys, tmp_path):
    with pytest.raises(SystemExit) as excinfo:
        main(["purge", str(tmp_path / "nope")])
    assert excinfo.value.code == 1
    assert "is not a directory" in capsys.readouterr().out


def test_purge_missing_blacklist_file(monkeypatch, capsys, tmp_path):
    project = make_project(tmp_path, {})
    (project / "blacklist.json").unlink()

    with pytest.raises(SystemExit) as excinfo:
        main(["purge", str(project)])
    assert excinfo.value.code == 1
    assert "Missing '" in capsys.readouterr().out
