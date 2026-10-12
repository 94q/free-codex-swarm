"""Trust boundaries and display-safe text. No credential file is ever read."""

from __future__ import annotations
import os
import re
import unicodedata

ANSI = re.compile(
    r"\x1b(?:\][^\x07\x1b]*(?:\x07|\x1b\\)|[PX^_].*?\x1b\\|\[[0-?]*[ -/]*[@-~]|[@-_])",
    re.DOTALL,
)
SECRETS = re.compile(
    r"(?i)(?:sk-[\w-]{8,}|Bearer\s+[\w.\-]+|eyJ[\w-]+\.[\w-]+\.[\w-]+)"
)
KEY_VALUE = re.compile(
    r'(?i)((?:access_token|refresh_token|id_token|api_key|password|authorization)["\s]*[:=]["\s]*)([^\s,"}]+)'
)


def safe_text(value: str) -> str:
    value = ANSI.sub("", str(value)).replace("\r\n", "\n").replace("\r", "")
    return "".join(
        c
        for c in value
        if c in "\n\t" or unicodedata.category(c) not in {"Cc", "Cf", "Cs"}
    )


def redact(value: str) -> str:
    return KEY_VALUE.sub(r"\1[REDACTED]", SECRETS.sub("[REDACTED]", safe_text(value)))


def child_env(home: str = "") -> dict[str, str]:
    env = {
        k: v
        for k, v in os.environ.items()
        if not any(
            x in k.upper()
            for x in ("API_KEY", "ACCESS_TOKEN", "AUTH_TOKEN", "REFRESH_TOKEN")
        )
    }
    if home:
        env["CODEX_HOME"] = home
    env["PYTHONIOENCODING"] = "utf-8"
    return env
