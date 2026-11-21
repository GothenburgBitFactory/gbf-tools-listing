"""Shared pytest fixtures."""

import os

import pytest


@pytest.fixture(autouse=True)
def hermetic_environment(monkeypatch):
    """Keep the test suite independent of the invoking user's environment."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.delenv("GITHUB_API_KEY", raising=False)
