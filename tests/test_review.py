"""Tests for the review command."""

import json
import os
import subprocess

import pytest

from tools_list import blacklist
from tools_list.cli import main
from tools_list.commands import review

COMMIT_DATE = "2026-01-02T12:00:00 +0000"


def git(directory, *args, check=True, date=COMMIT_DATE):
    env = dict(os.environ, GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
    result = subprocess.run(["git", *args], cwd=directory, capture_output=True, text=True, env=env)
    if check and result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")
    return result


def write_json(path, data):
    path.write_text(json.dumps(data, sort_keys=True, indent=4, ensure_ascii=False) + "\n")


def make_repo_project(tmp_path, blacklist, tools_data_history, dates=None):
    """A git project whose tools-data.json has one commit per history entry.

    `dates` optionally provides commit dates: the initial commit's, then one per history entry.
    """
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
    (directory / "include.json").write_text("{}")
    git(directory, "init", "-b", "main")
    git(directory, "config", "user.name", "Tester")
    git(directory, "config", "user.email", "tester@example.com")
    git(directory, "add", ".")
    git(directory, "commit", "-m", "initial", date=dates[0] if dates else COMMIT_DATE)
    for index, tools in enumerate(tools_data_history):
        (directory / "tools-data.json").write_text(json.dumps(tools, indent=2) + "\n")
        git(directory, "add", "tools-data.json")
        git(
            directory,
            "commit",
            "-m",
            f"tools {index}",
            date=dates[index + 1] if dates else COMMIT_DATE,
        )
    return directory


def fake_input(monkeypatch, *responses):
    responses = iter(responses)
    monkeypatch.setattr("builtins.input", lambda prompt: next(responses))


def patch_check_url(monkeypatch, mapping):
    def fake_check_url(url):
        return mapping.get(url, (200, url))

    monkeypatch.setattr(blacklist, "check_url", fake_check_url)


def patch_browser(monkeypatch):
    opened = []
    monkeypatch.setattr(review, "open_in_browser", lambda url: opened.append(url))
    return opened


def test_review_declined_leaves_state_unchanged(monkeypatch, capsys, tmp_path):
    project = make_repo_project(
        tmp_path,
        {"https://x/broken": "is broken"},
        [[{"url": "https://x/one"}], [{"url": "https://x/one"}, {"url": "https://x/two"}]],
    )
    patch_check_url(monkeypatch, {})
    patch_browser(monkeypatch)
    fake_input(monkeypatch, "n", "n")

    main(["review", str(project)])

    out = capsys.readouterr().out
    assert "No changes to" in out and "nothing to commit!" in out
    assert not (project / ".review-timestamp").exists()


def test_review_full_flow(monkeypatch, capsys, tmp_path):
    project = make_repo_project(
        tmp_path,
        {"https://x/broken": "is broken"},
        [[{"url": "https://x/one"}], [{"url": "https://x/one"}, {"url": "https://x/two"}]],
    )
    patch_check_url(monkeypatch, {})
    opened = patch_browser(monkeypatch)
    fake_input(monkeypatch, "y", "n", "y", "n", "y", "is a duplicate", "y")

    main(["review", str(project)])

    assert opened == ["https://x/broken", "https://x/one", "https://x/two"]
    timestamp = (project / ".review-timestamp").read_text().split()
    assert timestamp == [git(project, "log", "-1", "--format=%H", "--", "tools-data.json").stdout.strip()]
    blacklist = json.loads((project / "blacklist.json").read_text())
    assert blacklist == {"https://x/two": "is a duplicate"}
    subject = git(project, "log", "-1", "--format=%s").stdout.strip()
    assert subject.startswith("Update ") and subject.endswith("blacklist.json")


def test_review_twice_finds_nothing_new(monkeypatch, capsys, tmp_path):
    project = make_repo_project(tmp_path, {}, [[{"url": "https://x/one"}]])
    patch_check_url(monkeypatch, {})
    opened = patch_browser(monkeypatch)
    fake_input(monkeypatch, "y", "n")

    main(["review", str(project)])
    assert opened == ["https://x/one"]

    main(["review", str(project)])
    out = capsys.readouterr().out
    assert "No new tools found to review!" in out
    assert opened == ["https://x/one"]


def test_review_uncommitted_tools_data_records_nothing(monkeypatch, capsys, tmp_path):
    project = make_repo_project(tmp_path, {}, [])
    (project / "tools-data.json").write_text(json.dumps([{"url": "https://x/one"}], indent=2) + "\n")
    patch_check_url(monkeypatch, {})
    patch_browser(monkeypatch)

    main(["review", str(project)])

    out = capsys.readouterr().out
    assert "No new tools found to review!" in out
    assert not (project / ".review-timestamp").exists()


def test_review_purges_404_and_renames_urls(monkeypatch, capsys, tmp_path):
    project = make_repo_project(
        tmp_path,
        {
            "https://x/gone": "is gone",
            "https://x/renamed": "is renamed",
        },
        [[]],
    )
    patch_check_url(
        monkeypatch,
        {
            "https://x/gone": (404, "https://x/gone"),
            "https://x/renamed": (200, "https://x/newname"),
        },
    )
    patch_browser(monkeypatch)
    fake_input(monkeypatch, "y", "y", "y")

    main(["review", str(project)])

    out = capsys.readouterr().out
    assert "purging..." in out
    assert "was renamed to 'https://x/newname'" in out
    blacklist = json.loads((project / "blacklist.json").read_text())
    assert blacklist == {"https://x/newname": "is renamed"}


def test_review_since_commit(monkeypatch, capsys, tmp_path):
    project = make_repo_project(
        tmp_path,
        {"https://x/broken": "is broken"},
        [[{"url": "https://x/one"}], [{"url": "https://x/one"}, {"url": "https://x/two"}]],
    )
    patch_check_url(monkeypatch, {})
    opened = patch_browser(monkeypatch)
    since = git(project, "rev-parse", "--short", "HEAD~1").stdout.strip()
    fake_input(monkeypatch, "n", "y", "n")

    main(["review", str(project), "--since", since])

    assert opened == ["https://x/two"]
    assert (project / ".review-timestamp").exists()


def test_review_since_date(monkeypatch, capsys, tmp_path):
    dates = ["2025-12-31T12:00:00 +0000", "2026-01-01T12:00:00 +0000", "2026-01-15T12:00:00 +0000"]
    project = make_repo_project(
        tmp_path,
        {},
        [[{"url": "https://x/one"}], [{"url": "https://x/one"}, {"url": "https://x/two"}]],
        dates=dates,
    )
    patch_check_url(monkeypatch, {})
    opened = patch_browser(monkeypatch)
    fake_input(monkeypatch, "y", "n")

    main(["review", str(project), "--since", "2026-01-08"])

    out = capsys.readouterr().out
    assert opened == ["https://x/two"]
    assert "added since 2026-01-08" in out


def test_review_legacy_timestamp(monkeypatch, capsys, tmp_path):
    dates = ["2025-12-31T12:00:00 +0000", "2026-01-01T12:00:00 +0000", "2026-01-15T12:00:00 +0000"]
    project = make_repo_project(
        tmp_path,
        {},
        [[{"url": "https://x/one"}], [{"url": "https://x/one"}, {"url": "https://x/two"}]],
        dates=dates,
    )
    patch_check_url(monkeypatch, {})
    opened = patch_browser(monkeypatch)
    (project / ".review-timestamp").write_text("2026-01-08\n")
    fake_input(monkeypatch, "y", "n")

    main(["review", str(project)])

    out = capsys.readouterr().out
    assert opened == ["https://x/two"]
    assert "added since 2026-01-08" in out


def test_review_glitched_readd_is_not_new(monkeypatch, capsys, tmp_path):
    project = make_repo_project(
        tmp_path,
        {},
        [[{"url": "https://x/one"}], [], [{"url": "https://x/one"}]],
    )
    patch_check_url(monkeypatch, {})
    opened = patch_browser(monkeypatch)
    since = git(project, "rev-parse", "--short", "HEAD~2").stdout.strip()

    main(["review", str(project), "--since", since])

    out = capsys.readouterr().out
    assert opened == []
    assert "No new tools found to review!" in out


def test_review_invalid_since(monkeypatch, capsys, tmp_path):
    project = make_repo_project(tmp_path, {}, [[]])
    with pytest.raises(SystemExit) as excinfo:
        main(["review", str(project), "--since", "bogus"])
    assert excinfo.value.code == 1
    assert "Invalid --since value 'bogus'" in capsys.readouterr().out


def test_review_invalid_timestamp(monkeypatch, capsys, tmp_path):
    project = make_repo_project(tmp_path, {"https://x/broken": "is broken"}, [[]])
    patch_check_url(monkeypatch, {})
    patch_browser(monkeypatch)
    (project / ".review-timestamp").write_text("garbage\n")
    fake_input(monkeypatch, "n")

    with pytest.raises(SystemExit) as excinfo:
        main(["review", str(project)])
    assert excinfo.value.code == 1
    assert "does not contain a review commit SHA or date" in capsys.readouterr().out


def test_review_missing_tools_data(monkeypatch, capsys, tmp_path):
    project = make_repo_project(tmp_path, {"https://x/broken": "is broken"}, [[]])
    (project / "tools-data.json").unlink()
    patch_check_url(monkeypatch, {})

    with pytest.raises(SystemExit) as excinfo:
        main(["review", str(project)])
    assert excinfo.value.code == 1
    assert "Missing '" in capsys.readouterr().out
