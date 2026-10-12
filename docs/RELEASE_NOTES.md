# Codex-Swarm 0.2.0

## Windows quick start

Download **Codex-Swarm.exe** below, put it in a writable folder, and double-click it.
Windows 10/11 x64; no Python, pip, installer, ZIP extraction, or administrator rights required.
Git and the official native Codex CLI with ChatGPT sign-in are still required to run agent tasks.

The compressed one-file application unpacks its bundled runtime into a temporary directory
at startup. Persistent settings/history and license notices are created in
`codex-swarm-data` beside the EXE. Move that folder together with the EXE to preserve state.
Codex login credentials remain in the official CLI's credential home, not this folder.

This executable is unsigned. Windows may show a publisher/reputation warning. Review
the source and SHA256SUMS.txt; do not disable antivirus or run as administrator.

## Other changes

- Windows source instructions renamed to **Setup for Windows**.
- Linux and macOS source setup, portable POSIX launch/install scripts, and platform-native state paths.
- Windows-only sandbox configuration is no longer passed to POSIX Codex processes.
- Automated Windows/Linux/macOS test matrix; offline EXE TUI smoke test.
- Bundled project/dependency license notices; reproducible build procedure in docs/BUILDING.md.

The EXE does not bundle Git, Codex, project build tools, or account access. Models and
usage allowances depend on your authorized account. The supplied cat's provenance
limitations are documented in THIRD_PARTY_NOTICES.md. Linux/macOS are source releases;
native agent runs on those platforms have not been live-tested by the maintainer.
