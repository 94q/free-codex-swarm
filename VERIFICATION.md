# Verification

## Local release checks

- **117 automated tests passed** in 31.02 seconds on Windows / Python 3.13.
- Ruff undefined-name/unused-import checks passed.
- Python compilation and an installable wheel build passed.
- Normal tests do not need a Codex login or make live provider calls. They use mocked provider behavior plus real temporary Git/process fixtures.
- Coverage includes scheduling, worktree isolation, integration/promotion safeguards, locks, cancellation, checkpoints, theme persistence, 16 palettes, cat artwork, centered headings, resizing/fallback logic, settings reset, and installer behavior.

## Earlier live execution

Two independent Codex worker processes were live-tested with one existing ChatGPT-authenticated account, isolated worktrees, coordinator planning/final review, fixture tests, and explicit promotion. Cancellation left no observed descendants. Those runs used an explicitly selected unelevated Windows sandbox after elevated sandbox setup failed locally.

This is limited fixture evidence, not production certification. Independently authenticated multiple accounts and macOS/Linux were not live-verified. CLI/model access and sandbox behavior vary by account and installation.

## Public distribution

The upload bundle intentionally excludes private machine paths, auth caches, settings, history databases, task logs/worktrees, virtual environments, raw historical live evidence, and generated build output. The preview uses a generic identity.

A Windows GitHub Actions workflow is included for Python 3.11 and 3.13. Its remote execution has not been verified because this repository has not yet been uploaded. See CONTRIBUTING.md to reproduce the normal suite.

## Fresh installation check

A separate clean copy in a directory containing spaces was installed using `install_requirements.bat --no-pause`. A new venv was created, dependencies installed, `pip check` passed, `run.bat --help` succeeded, and a headless TUI/theme smoke passed. Re-running the installer also succeeded. After installing development dependencies, **117 tests passed in 29.86 seconds** with application-data locations redirected to empty fixture directories. No live Codex inference was performed for these packaging checks.

The clean upload folder was audited for private usernames/paths, credential/state files, generated environments/build files, and broken relative Markdown file links. All checks passed.
