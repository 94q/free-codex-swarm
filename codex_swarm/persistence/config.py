from __future__ import annotations
import copy
import getpass
import ipaddress
import json
import os
from pathlib import Path
import re
import secrets
import sys
from datetime import datetime, timezone
from codex_swarm.core.security import safe_text

COLORS = dict(
    background="#0B0B0B",
    text="#FFFFFF",
    accent="#98FB98",
    secondary="#74D99B",
    border="#98FB98",
    error="#FF7777",
    warning="#FFC66D",
)
THEMES = {
    "classic_pale_green": COLORS,
    "matrix_green": {
        **COLORS,
        "accent": "#00FF41",
        "border": "#008F11",
        "secondary": "#5CFF85",
    },
    "ice_blue": {
        **COLORS,
        "accent": "#96DDFF",
        "border": "#65B8E8",
        "secondary": "#B9E9FF",
    },
    "cyber_purple": {
        **COLORS,
        "accent": "#D7A6FF",
        "border": "#A670D6",
        "secondary": "#BC83FC",
    },
    "crimson_terminal": {
        **COLORS,
        "accent": "#FF6E80",
        "border": "#C9475C",
        "secondary": "#FFA5AE",
    },
    "monochrome": {
        **COLORS,
        "accent": "#FFFFFF",
        "border": "#AAAAAA",
        "secondary": "#CCCCCC",
    },
    "amber_console": {
        **COLORS,
        "accent": "#FFBF69",
        "border": "#D99038",
        "secondary": "#FFDDA1",
    },
    "ocean_depths": {
        **COLORS,
        "background": "#071923",
        "accent": "#5EDDD3",
        "border": "#268A99",
        "secondary": "#A2D6E8",
    },
    "rose_quartz": {
        **COLORS,
        "background": "#1A1019",
        "accent": "#FFA8C5",
        "border": "#C778A1",
        "secondary": "#EAC2DF",
    },
    "tokyo_night": {
        **COLORS,
        "background": "#1A1B26",
        "text": "#C0CAF5",
        "accent": "#7AA2F7",
        "border": "#565F89",
        "secondary": "#BB9AF7",
    },
    "dracula": {
        **COLORS,
        "background": "#282A36",
        "text": "#F8F8F2",
        "accent": "#BD93F9",
        "border": "#6272A4",
        "secondary": "#FF79C6",
    },
    "nord": {
        **COLORS,
        "background": "#2E3440",
        "text": "#ECEFF4",
        "accent": "#88C0D0",
        "border": "#81A1C1",
        "secondary": "#A3BE8C",
    },
    "gruvbox": {
        **COLORS,
        "background": "#282828",
        "text": "#EBDBB2",
        "accent": "#FABD2F",
        "border": "#D79921",
        "secondary": "#B8BB26",
    },
    "catppuccin_mocha": {
        **COLORS,
        "background": "#1E1E2E",
        "text": "#CDD6F4",
        "accent": "#CBA6F7",
        "border": "#89B4FA",
        "secondary": "#F5C2E7",
    },
    "sunset_glow": {
        **COLORS,
        "background": "#1D1217",
        "accent": "#FF9E64",
        "border": "#E06C75",
        "secondary": "#FFC8A4",
    },
    "mint_terminal": {
        **COLORS,
        "background": "#0E1A17",
        "accent": "#8BE9B0",
        "border": "#4DAD8F",
        "secondary": "#A7E8DB",
    },
}


def appearance() -> dict:
    return {
        "theme": "classic_pale_green",
        **COLORS,
        "ascii_art": "default",
        "custom_art": "",
        "ascii_enabled": True,
        "ascii_centered": True,
        "gradient": {
            "enabled": True,
            "start": "#FFFFFF",
            "end": "#98FB98",
            "direction": "vertical",
            "scope": ["banner"],
        },
    }


def profile(index: int) -> dict:
    return {
        "id": f"session_{index:02d}",
        "display_name": "Brain" if index == 1 else f"Worker slot {index - 1}",
        "enabled": True,
        "role": "coordinator" if index == 1 else "worker",
        "codex_home": "",
        "preferred_model": "auto",
        "reasoning": "auto",
    }


def defaults() -> dict:
    return {
        "version": 1,
        "appearance": appearance(),
        "custom_themes": {},
        "prompt": {
            "username": getpass.getuser(),
            "ip": f"192.168.{secrets.randbelow(256)}.{secrets.randbelow(254) + 1}",
        },
        "sessions": {
            "configured_slots": 4,
            "maximum_slots": 8,
            "profiles": [profile(i) for i in range(1, 5)],
        },
        "engine": {
            "mode": "auto",
            "coordinator_model": "auto",
            "coordinator_effort": "high",
            "maximum_concurrent_workers": 3,
            "invocation_budget": 12,
            "retry_budget": 1,
            "timeout_seconds": 900,
            "permission": "read-only",
            "windows_sandbox": "elevated",
            "codex_binary": "",
        },
        "projects": [],
        "selected_project": "",
        "command_history": [],
    }


def data_dir() -> Path:
    # Keep upgrades on the same settings/history and instance lock, without
    # moving a directory that may contain active Git worktrees.
    for name in ("CODEX_SWARM_HOME", "NEXUS_HOME"):
        if os.environ.get(name):
            return Path(os.environ[name]).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "codex-swarm-data"
    if sys.platform == "darwin":
        base = Path.home() / "Library/Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local")))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share")))
    legacy = base / "CodexNexus"
    if legacy.is_dir():
        return legacy
    return base / "CodexSwarm"


def merge(base: dict, patch: dict) -> dict:
    if not isinstance(patch, dict):
        raise ValueError("Configuration must be a JSON object")
    result = copy.deepcopy(base)
    for key, value in patch.items():
        result[key] = (
            merge(result[key], value)
            if isinstance(value, dict) and isinstance(result.get(key), dict)
            else value
        )
    return result


def validate_appearance(a: dict) -> None:
    for name in COLORS:
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", a[name]):
            raise ValueError(f"Invalid {name}: use #RRGGBB")
    g = a["gradient"]
    for key in ("start", "end"):
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", g[key]):
            raise ValueError("Invalid gradient color")
    if g["direction"] not in {
        "vertical",
        "vertical_reverse",
        "horizontal",
        "horizontal_reverse",
    }:
        raise ValueError("Invalid gradient direction")
    if not isinstance(g["scope"], list) or not set(g["scope"]) <= {
        "banner",
        "headings",
        "borders",
    }:
        raise ValueError("Gradient scopes: banner, headings, borders")
    if len(a["custom_art"]) > 100_000:
        raise ValueError("Artwork limit is 100,000 characters")
    a["custom_art"] = safe_text(a["custom_art"])


def validate(c: dict) -> None:
    if not isinstance(c, dict):
        raise ValueError("Configuration must be an object")
    for key in ("appearance", "prompt", "sessions", "engine", "custom_themes"):
        if not isinstance(c.get(key), dict):
            raise ValueError(f"{key} must be an object")
    validate_appearance(c["appearance"])
    ipaddress.IPv4Address(c["prompt"]["ip"])
    if not re.fullmatch(r"[^\s@:$\x00-\x1f]{1,48}", c["prompt"]["username"]):
        raise ValueError(
            "Username must be 1-48 plain characters, without spaces, @, :, or $."
        )
    s, e = c["sessions"], c["engine"]
    for k in ("configured_slots", "maximum_slots"):
        if type(s.get(k)) is not int:
            raise ValueError(f"{k} must be an integer")
    for k in (
        "maximum_concurrent_workers",
        "invocation_budget",
        "retry_budget",
        "timeout_seconds",
    ):
        if type(e.get(k)) is not int:
            raise ValueError(f"{k} must be an integer")
    if not isinstance(s.get("profiles"), list) or any(
        not isinstance(p, dict) for p in s["profiles"]
    ):
        raise ValueError("Profiles must be a list of objects")
    if not 2 <= s["configured_slots"] <= s["maximum_slots"]:
        raise ValueError("Session count must be between 2 and maximum_slots")
    if s["maximum_slots"] < 5:
        raise ValueError("Maximum slots must be at least 5")
    if len(s["profiles"]) != s["configured_slots"]:
        raise ValueError("Profile count must match configured_slots")
    ids = [p["id"] for p in s["profiles"]]
    if len(ids) != len(set(ids)) or any(
        not re.fullmatch(r"[a-zA-Z0-9_-]{1,48}", x) for x in ids
    ):
        raise ValueError("Profile IDs must be unique safe names")
    if sum(p["enabled"] and p["role"] == "coordinator" for p in s["profiles"]) != 1:
        raise ValueError("Enable exactly one coordinator")
    for p in s["profiles"]:
        if p["role"] not in {"coordinator", "worker", "unassigned"}:
            raise ValueError("Invalid session role")
        if not isinstance(p["enabled"], bool):
            raise ValueError("Enabled must be true or false")
        if p["codex_home"] and not Path(p["codex_home"]).expanduser().is_absolute():
            raise ValueError("CODEX_HOME must be an absolute directory")
        if any(
            not isinstance(p.get(k), str)
            for k in ("display_name", "preferred_model", "reasoning", "codex_home")
        ):
            raise ValueError(
                "Profile names, models, effort and CODEX_HOME must be strings"
            )
        if (
            p["codex_home"]
            and Path(p["codex_home"]).exists()
            and not Path(p["codex_home"]).is_dir()
        ):
            raise ValueError("CODEX_HOME must be a directory")
    if not 1 <= e["maximum_concurrent_workers"] <= s["maximum_slots"]:
        raise ValueError("Concurrency must be 1..maximum_slots")
    if e["mode"] not in {"auto", "eco", "performance", "manual"}:
        raise ValueError("Unknown mode")
    if e["permission"] not in {"read-only", "workspace-write"}:
        raise ValueError("Only sandboxed permissions are supported")
    if e["windows_sandbox"] not in {"elevated", "unelevated"}:
        raise ValueError(
            "Windows sandbox must be elevated or unelevated; no automatic fallback"
        )
    if not 2 <= e["invocation_budget"] <= 100:
        raise ValueError("Invocation budget: 2..100")
    if not 0 <= e["retry_budget"] <= 3:
        raise ValueError("Retry budget: 0..3")
    if not 10 <= e["timeout_seconds"] <= 14400:
        raise ValueError("Timeout: 10..14400 seconds")
    for custom in c["custom_themes"].values():
        validate_appearance(custom)


class Config:
    def __init__(self, root: Path | None = None):
        self.root = root or data_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "settings.json"
        self.warning = ""
        self.value = defaults()
        if self.path.exists():
            try:
                self.value = merge(
                    self.value, json.loads(self.path.read_text(encoding="utf-8"))
                )
                validate(self.value)
            except (ValueError, TypeError, KeyError, OSError) as exc:
                self.warning = (
                    f"Invalid configuration; loaded defaults. Original preserved: {exc}"
                )
                self.value = defaults()
        else:
            self.save()

    def save(self, value: dict | None = None) -> None:
        candidate = copy.deepcopy(value if value is not None else self.value)
        validate(candidate)
        if self.warning and self.path.exists():
            backup = self.path.with_name("settings.invalid.json")
            if not backup.exists():
                backup.write_bytes(self.path.read_bytes())
        temp = self.path.with_suffix(".tmp")
        temp.write_text(
            json.dumps(candidate, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(temp, self.path)
        self.value = candidate

    def reset(self) -> Path | None:
        """Reset preferences, not official authentication or preserved task data.

        The caller must hold the instance lock before changing live settings.
        """
        backup = None
        if self.path.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
            backup = self.root / f"settings.before-reset-{stamp}.json"
            backup.write_bytes(self.path.read_bytes())
        self.warning = ""
        self.save(defaults())
        return backup

    def resize(self, count: int) -> None:
        c = copy.deepcopy(self.value)
        s = c["sessions"]
        if not 2 <= count <= s["maximum_slots"]:
            raise ValueError("Requested slots outside configured limits")
        profiles = s["profiles"][:count]
        n = 1
        while len(profiles) < count:
            if f"session_{n:02d}" not in {p["id"] for p in profiles}:
                p = profile(n)
                p["role"] = "worker"
                profiles.append(p)
            n += 1
        s["profiles"], s["configured_slots"] = profiles, count
        self.save(c)
