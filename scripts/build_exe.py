"""Build a compressed one-file console executable; run on Windows x64."""
from __future__ import annotations

import hashlib
from importlib import metadata
from pathlib import Path
import shutil
import subprocess
import sys

from packaging.requirements import Requirement


def collect_licenses(root: Path) -> Path:
    target = root / "build" / "licenses"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("LICENSE", "THIRD_PARTY_NOTICES.md"):
        shutil.copy2(root / name, target / name)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if python_license.is_file():
        shutil.copy2(python_license, target / "PYTHON-LICENSE.txt")
    pending = [("codex-swarm", set()), ("pyinstaller", set())]
    seen = set()
    while pending:
        name, extras = pending.pop()
        dist = metadata.distribution(name)
        key = dist.metadata["Name"].lower().replace("_", "-")
        visit = (key, tuple(sorted(extras)))
        if visit in seen:
            continue
        seen.add(visit)
        folder = target / key
        folder.mkdir(exist_ok=True)
        (folder / "METADATA.txt").write_text(dist.read_text("METADATA") or "", encoding="utf-8")
        for item in dist.files or []:
            if any(word in item.name.lower() for word in ("license", "copying", "notice")):
                source = Path(dist.locate_file(item))
                if source.is_file():
                    destination = folder / str(item).replace("..", "_")
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, destination)
        for req in dist.requires or []:
            parsed = Requirement(req)
            if parsed.marker is None or any(parsed.marker.evaluate({"extra": extra}) for extra in {"", *extras}):
                pending.append((parsed.name, parsed.extras))
    return target


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("Build the Windows EXE on Windows; PyInstaller is not a cross-compiler.")
    root = Path(__file__).resolve().parents[1]
    licenses = collect_licenses(root)
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
        "--onefile", "--console", "--noupx", "--name", "Codex-Swarm",
        "--distpath", str(root / "dist"), "--workpath", str(root / "build" / "pyinstaller"),
        "--specpath", str(root / "build"), "--paths", str(root),
        "--collect-all", "textual", "--collect-all", "rich",
        "--copy-metadata", "codex-swarm",
        "--add-data", f"{licenses}:licenses", str(root / "main.py"),
    ], cwd=root, check=True)
    exe = root / "dist" / "Codex-Swarm.exe"
    digest = hashlib.sha256(exe.read_bytes()).hexdigest()
    (exe.parent / "SHA256SUMS.txt").write_text(f"{digest}  {exe.name}\n", encoding="utf-8")
    print(f"Built {exe.name}: {exe.stat().st_size / 1024 / 1024:.1f} MiB")


if __name__ == "__main__":
    main()
