# Building the Windows release

Use Windows x64 and Python 3.13 x64. PyInstaller builds for the current OS;
it does not cross-compile a Windows EXE from Linux/macOS.

```powershell
py -3.13 -m venv .build-venv
& .\.build-venv\Scripts\python.exe -m pip install -r requirements-build.txt
& .\.build-venv\Scripts\python.exe scripts/build_exe.py
& .\dist\Codex-Swarm.exe --self-test
```

Outputs: `dist/Codex-Swarm.exe` and `dist/SHA256SUMS.txt`. The self-test creates
portable state beside the EXE; do not publish that state. Publish only the EXE
and checksum file. The console is intentional: this is a terminal application.

PyInstaller's one-file archive compresses the bundled Python/runtime modules.
UPX is deliberately disabled to reduce corruption/antivirus problems. Runtime
unpacking is temporary; persisted app state uses the EXE's real directory, not
the unpacking directory. No embedded credentials, Codex CLI, or Git are included.
Project and dependency license files are collected into the bundle and extracted
into the portable state folder on launch. No signing certificate is configured.

The tag-triggered `.github/workflows/release.yml` builds/tests on Windows,
runs the offline frozen TUI without Python/Codex on PATH, generates SHA-256,
and publishes the two release assets using GitHub's scoped job token.

For a new release: update version and release notes, commit, push the source,
then push a new version tag. Never replace an existing published release silently.
The build procedure is repeatable, but binaries are not promised byte-for-byte
reproducible across dependency updates or different toolchains.
