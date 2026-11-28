import pytest

from tools_list.cli import main


def test_command_is_required(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


def test_unknown_command_fails(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["frobnicate", "task"])
    assert excinfo.value.code == 2


def test_help(capsys):
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    out = capsys.readouterr().out
    assert "update" in out
    assert "review" in out
    assert "purge" in out


def test_update_rejects_missing_directory(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("GITHUB_API_KEY", "dummy")
    with pytest.raises(SystemExit) as excinfo:
        main(["update", str(tmp_path / "nope")])
    assert excinfo.value.code == 1
    assert "is not a directory" in capsys.readouterr().out
