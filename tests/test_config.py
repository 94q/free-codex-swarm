import pytest
from codex_swarm.persistence.config import Config, validate, defaults, data_dir
from codex_swarm.core.security import safe_text, redact, child_env
from codex_swarm.tui.banner import (
    banner,
    gradient,
    mix,
    ASCII_ART,
    art_size,
    recommended_size,
)
from rich.cells import cell_len


@pytest.mark.parametrize(
    "mode", ["fresh", "legacy", "legacy_env", "new_env", "both_env"]
)
def test_renamed_state_directory(tmp_path, monkeypatch, mode):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("NEXUS_HOME", raising=False)
    monkeypatch.delenv("CODEX_SWARM_HOME", raising=False)
    expected = tmp_path / "CodexSwarm"
    if mode == "legacy":
        expected = tmp_path / "CodexNexus"
        original = Config(expected)
        original.value["engine"]["mode"] = "eco"
        original.save()
    if mode in {"legacy_env", "both_env"}:
        expected = tmp_path / "legacy-custom"
        monkeypatch.setenv("NEXUS_HOME", str(expected))
    if mode in {"new_env", "both_env"}:
        expected = tmp_path / "swarm-custom"
        monkeypatch.setenv("CODEX_SWARM_HOME", str(expected))
    assert data_dir() == expected
    if mode == "legacy":
        assert Config().value["engine"]["mode"] == "eco"
        assert not (tmp_path / "CodexSwarm").exists()


@pytest.mark.parametrize("count", [2, 3, 4, 5, 8, 12])
def test_slot_roundtrip(tmp_path, count):
    c = Config(tmp_path)
    c.value["sessions"]["maximum_slots"] = 12
    c.save()
    c.resize(count)
    restored = Config(tmp_path)
    assert restored.value["sessions"]["configured_slots"] == count
    assert len(restored.value["sessions"]["profiles"]) == count


def test_bad_config_preserved(tmp_path):
    (tmp_path / "settings.json").write_text("{broken")
    c = Config(tmp_path)
    assert c.warning
    c.save()
    assert (tmp_path / "settings.invalid.json").read_text() == "{broken"


def test_prompt_persistent(tmp_path):
    c = Config(tmp_path)
    assert Config(tmp_path).value["prompt"] == c.value["prompt"]


def test_roles_and_enabled(tmp_path):
    c = Config(tmp_path)
    p = c.value["sessions"]["profiles"]
    p[0]["role"] = "worker"
    p[1]["role"] = "coordinator"
    p[2]["enabled"] = False
    c.save()
    assert Config(tmp_path).value["sessions"]["profiles"][1]["role"] == "coordinator"


@pytest.mark.parametrize(
    "key,value",
    [
        ("permission", "danger-full-access"),
        ("mode", "fake"),
        ("maximum_concurrent_workers", 0),
        ("retry_budget", 4),
        ("timeout_seconds", 1),
        ("invocation_budget", 1),
    ],
)
def test_invalid_engine(key, value):
    c = defaults()
    c["engine"][key] = value
    with pytest.raises(ValueError):
        validate(c)


@pytest.mark.parametrize("color", ["green", "#FF", "#ZZZZZZ", "#1234567"])
def test_invalid_colors(color):
    c = defaults()
    c["appearance"]["accent"] = color
    with pytest.raises(ValueError):
        validate(c)


def test_art_sanitized():
    text = "  ⣿\n\x1b[31mGREEN\x1b[0m\x1b]52;c;SECRET\x07\x00\u202e"
    assert safe_text(text) == "  ⣿\nGREEN"


def test_redaction(monkeypatch):
    assert "sk-abc123456789" not in redact("api_key=sk-abc123456789")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    assert "OPENAI_API_KEY" not in child_env()


@pytest.mark.parametrize("width", [12, 24, 40, 80, 120])
def test_banner_width(width):
    b = banner(defaults()["appearance"], width)
    # Small terminals now scroll the full art rather than replacing it.
    assert [line.lstrip() for line in b.plain.splitlines()] == [
        line.lstrip() for line in ASCII_ART.splitlines()
    ]
    art_width = art_size(defaults()["appearance"])[0]
    assert max(map(cell_len, b.plain.splitlines())) == art_width + max(
        0, (width - art_width) // 2
    )


def test_art_dimensions_and_startup_size():
    a = defaults()["appearance"]
    assert recommended_size(a) == (120, 44)
    a.update(ascii_art="custom", custom_art="界" * 100 + "\n" + "\n".join(["cat"] * 39))
    assert art_size(a) == (200, 40)
    assert recommended_size(a) == (208, 72)
    a["ascii_enabled"] = False
    assert art_size(a) == (0, 0)
    assert recommended_size(a) == (120, 44)


def test_reset_preferences_with_backup(tmp_path):
    c = Config(tmp_path)
    c.value["appearance"]["theme"] = "cyber_purple"
    c.value["engine"]["mode"] = "eco"
    c.value["projects"] = ["old project"]
    c.value["command_history"] = ["help"]
    c.save()
    old_bytes = c.path.read_bytes()
    record = tmp_path / "preserved-task.txt"
    record.write_text("keep")
    backup = c.reset()
    assert backup.read_bytes() == old_bytes
    assert c.value["appearance"] == defaults()["appearance"]
    assert c.value["engine"]["mode"] == "auto"
    assert c.value["projects"] == c.value["command_history"] == []
    assert record.read_text() == "keep"
    assert Config(tmp_path).value == c.value


def test_gradient_endpoints():
    assert mix("#FFFFFF", "#98FB98", 0) == "#ffffff"
    assert mix("#FFFFFF", "#98FB98", 1) == "#98fb98"
    a = defaults()["appearance"]
    t = gradient("one\ntwo", a)
    assert str(t.spans[0].style) == "#ffffff"
    assert str(t.spans[-1].style) == "#98fb98"
