"""Install the local project without requiring PowerShell script permissions."""

from __future__ import annotations
import os
from pathlib import Path
import shutil
import subprocess
import sys


def venv_python(root: Path) -> Path:
    return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def install(root: Path) -> None:
    if sys.version_info < (3, 11):
        raise RuntimeError(
            "Python 3.11 or newer is required. Install it, then rerun this installer."
        )
    python = venv_python(root)
    if not python.exists():
        print("Creating a local .venv ...", flush=True)
        subprocess.run([sys.executable, "-m", "venv", str(root / ".venv")], check=True)
    subprocess.run(
        [
            str(python),
            "-c",
            "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)",
        ],
        check=True,
    )
    print("Installing Codex-Swarm and its Python dependencies ...", flush=True)
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", "requirements.txt"],
        cwd=root,
        check=True,
    )
    subprocess.run([str(python), "-m", "pip", "check"], cwd=root, check=True)
    if not shutil.which("git"):
        print("Note: Git is not on PATH. Install Git before running tasks.")
    print(
        "Installation complete. Run run.bat (Windows) or sh run.sh (Linux/macOS), then check Codex login and models in the app."
    )


def main() -> int:
    try:
        install(Path(__file__).resolve().parents[1])
        return 0
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        print(
            "Check Python 3.11+, internet access, and the error above. No system policy was changed.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
