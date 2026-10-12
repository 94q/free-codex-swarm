import sys
from pathlib import Path

import pytest

from codex_swarm.persistence.config import data_dir


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    for name in ("CODEX_SWARM_HOME", "NEXUS_HOME", "XDG_DATA_HOME"):
        monkeypatch.delenv(name, raising=False)


def test_frozen_state_is_next_to_executable(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(tmp_path / "Codex-Swarm.exe"))
    assert data_dir() == tmp_path / "codex-swarm-data"


def test_explicit_home_wins_over_portable(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("CODEX_SWARM_HOME", str(tmp_path))
    assert data_dir() == tmp_path


@pytest.mark.parametrize("platform, suffix", [
    ("linux", ".local/share/CodexSwarm"),
    ("darwin", "Library/Application Support/CodexSwarm"),
])
def test_platform_state_directory(tmp_path, monkeypatch, platform, suffix):
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert data_dir() == tmp_path / suffix


def test_linux_xdg_state(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    assert data_dir() == tmp_path / "CodexSwarm"
