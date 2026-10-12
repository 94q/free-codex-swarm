from codex_swarm.tui.terminal import resize_with_backend, fit_terminal
from codex_swarm.persistence.config import (
    Config,
    THEMES,
    appearance,
    validate_appearance,
)
import pytest


class Console:
    def __init__(
        self, size=(80, 25, 80, 300), largest=(180, 70), buffer_ok=True, window_ok=True
    ):
        self.size, self.maximum = size, largest
        self.buffer_ok, self.window_ok = buffer_ok, window_ok
        self.calls = []

    def dimensions(self):
        return self.size

    def largest(self):
        return self.maximum

    def set_buffer(self, width, height):
        self.calls.append(("buffer", width, height))
        return self.buffer_ok

    def set_window(self, width, height):
        self.calls.append(("window", width, height))
        return self.window_ok


def test_resize_grows_buffer_before_window():
    c = Console()
    result = resize_with_backend(c, (120, 44))
    assert result.resized and result.size == (120, 44)
    assert c.calls == [("buffer", 120, 300), ("window", 120, 44)]


def test_resize_clamps_to_display():
    c = Console(largest=(100, 40))
    result = resize_with_backend(c, (208, 72))
    assert result.size == (100, 40)
    assert "scroll" in result.notice
    assert c.calls[-1] == ("window", 100, 40)


def test_resize_keeps_already_larger_window():
    c = Console(size=(140, 60, 140, 300))
    result = resize_with_backend(c, (120, 44))
    assert not result.resized
    assert result.size == (140, 60)
    assert c.calls == []


@pytest.mark.parametrize(
    "options", [{"buffer_ok": False}, {"window_ok": False}, {"largest": (0, 0)}]
)
def test_resize_failure_nonfatal(options):
    result = resize_with_backend(Console(**options), (120, 44))
    assert not result.resized
    assert "scrollable" in result.notice


def test_windows_terminal_is_not_resized(monkeypatch):
    monkeypatch.setenv("WT_SESSION", "test-terminal")
    assert not fit_terminal((120, 44)).resized


@pytest.mark.parametrize("theme", THEMES)
def test_all_themes_valid(theme):
    a = appearance()
    a.update(THEMES[theme])
    validate_appearance(a)


@pytest.mark.parametrize("queued", [False, True])
def test_cli_reset_applied_before_ui(tmp_path, monkeypatch, queued):
    from codex_swarm.__main__ import main
    from codex_swarm.tui.app import SwarmApp

    c = Config(tmp_path)
    c.value["engine"]["mode"] = "eco"
    c.save()
    args = ["codex-swarm", "--home", str(tmp_path), "--no-resize"]
    if queued:
        (tmp_path / "reset-settings.request").write_text("reset")
    else:
        args.append("--reset-settings")
    monkeypatch.setattr("sys.argv", args)
    seen = []
    monkeypatch.setattr(
        SwarmApp, "run", lambda self: seen.append(self.config.value["engine"]["mode"])
    )
    main()
    assert seen == ["auto"]
    assert not (tmp_path / "reset-settings.request").exists()
    assert len(list(tmp_path.glob("settings.before-reset-*.json"))) == 1
