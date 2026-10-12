# Contributing

Small, focused fixes and improvements are welcome.

1. Fork and clone the repository; create a branch for your change.
2. Run `install_requirements.bat` (Windows) or `sh install_requirements.sh` (Linux/macOS), then install `requirements-dev.txt` with the venv's Python.
3. Make a focused change and add regression tests.
4. Run `python -m pytest -q` and `python -m ruff check codex_swarm scripts tests --select F` using the venv.
5. Open a pull request describing the behavior, tests, and any limits.

Keep read-only defaults, bounded execution, isolated worktrees, explicit promotion,
and official authentication intact. Do not add account creation, quota bypass,
credential scraping, silent sandbox weakening, or automatic identity rotation.

Never commit `.venv`, state databases, credentials, private prompts, or task logs.
The normal suite must run without a ChatGPT login. Live tests are opt-in and must
not run in ordinary CI. Do not claim support for platforms you have not tested.

Original contributions are submitted under the project's MIT license. Preserve
third-party notices; do not submit artwork or other material without appropriate rights.
