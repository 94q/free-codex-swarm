<div align="center">

# Codex-Swarm

**One task. Multiple agents. One terminal.**

A terminal command center for parallel Codex development with ChatGPT sign-in,
isolated Git worktrees, and a review-first workflow.

![python](https://img.shields.io/badge/python-3.11%2B-blue)
![platform](https://img.shields.io/badge/platform-windows%20%7C%20linux%20%7C%20macOS-blue)
![license](https://img.shields.io/badge/license-MIT-green)

</div>

## Put multiple ChatGPT sessions to work together

**The idea: several independent ChatGPT accounts, one coordinated development swarm.**
If a regional ChatGPT free trial or promotion is available to you, and its terms
permit your use, eligible accounts with Codex access can be configured as separate
worker sessions. Codex-Swarm coordinates their assignments and brings their work
together: parallel implementation, different approaches, and a final review of
the combined result.

Authenticate each account independently using its own `codex_home`; see
[session setup](#accounts-and-process-slots). This combines **work and perspectives**,
not account balances or model intelligence. Each account keeps its own access and
usage limits. Do not assume that creating extra accounts grants extra trials or
that any particular offer is available in your region. One account with multiple
worker slots also works.

![Codex-Swarm terminal interface](assets/terminal-preview.png)

> **free-codex-swarm** is the repository name; **Codex-Swarm** is the application name.
> The software is free and open source. Codex access, model availability, and usage
> allowances depend on your account. This project does not provide trials, unlimited
> usage, or automatic account rotation. It is an independent project, not an OpenAI product.

## Why use it?

- **Parallel workers:** a coordinator breaks your objective into focused assignments.
- **Isolated edits:** workers use separate Git worktrees; your original checkout stays unchanged until promotion.
- **Review before merge:** integration is serialized, followed by a final review and explicit confirmation.
- **Real visibility:** live agent states, event logs, token telemetry when available, and saved reports.
- **Flexible sessions:** one ChatGPT login with multiple process slots, or independently configured credential homes.
- **Make it yours:** 16 themes, editable ASCII art, gradients, centered headings, and the default cat.
- **No API key required:** this app uses official Codex CLI with ChatGPT authentication.

```text
objective -> coordinator plan -> parallel workers -> integration -> review -> your approval
```

## Requirements

| Requirement | Details |
| --- | --- |
| Operating system | Windows 10/11 x64 for the EXE; Windows, Linux, or macOS for source setup. |
| Python | Not needed for the EXE. Source setup needs Python 3.11+, pip, and venv. |
| Git | Installed and available on PATH. Projects need an initial commit and a clean working tree. |
| Codex CLI | A recent official native CLI supporting `exec`, `app-server`, and the flags used by this release. |
| ChatGPT sign-in | An account with working Codex access. No particular free/trial entitlement is promised. |
| Internet | Needed to install dependencies, sign in, and run Codex. |
| Project tools | Install your project's language runtimes/test tools separately. |

[Download Python](https://www.python.org/downloads/windows/) ·
[Download Git](https://git-scm.com/downloads/win) ·
[Official Codex installation guide](https://learn.chatgpt.com/docs/codex/cli)

The Python installer should include the launcher or add Python to PATH. Reopen your
terminal after installing prerequisites. Administrator access is not required by the
app's installer. Linux/macOS source paths are supported and covered by CI; live agent
runs on those platforms have not been verified by the maintainer. See [LIMITATIONS.md](LIMITATIONS.md).

## Quick start from Windows

**[Download Codex-Swarm.exe](https://github.com/94q/free-codex-swarm/releases/latest/download/Codex-Swarm.exe)**
· [All releases and checksums](https://github.com/94q/free-codex-swarm/releases/latest)

1. Download the **single EXE** and put it in a writable folder (Downloads is fine).
   No ZIP extraction, Python installation, pip, or app installer is needed.
2. If not already installed, install **Git** and the **official Codex CLI** using the
   links in Requirements. Then run `codex login` and choose ChatGPT sign-in.
3. Double-click **Codex-Swarm.exe**. Select your clean Git project and start a task.

The EXE bundles Python and the app's Python dependencies, **not Git, Codex, or
project build tools**. Internet/account access is still required for agent tasks.
Only Windows 10/11 **x64** is provided as a binary; other architectures use source setup.

On first launch it automatically creates **`codex-swarm-data` beside the EXE**, containing
`settings.json`, `history.sqlite3`, an instance lock, license notices, and task files
as needed. Keep the EXE and that folder together when moving/upgrading. Treat this
folder as private: it can contain project paths, prompts, logs, and reports. Official
Codex credentials stay in the CLI's own credential home. Use `--home` or
`CODEX_SWARM_HOME` if you want state elsewhere. Do not launch it from a read-only folder.

The executable is a compressed one-file bundle; it briefly extracts its runtime
into the system temporary directory at startup, not into your download folder.
It is **unsigned**: Windows may show a publisher/reputation warning. Review the
release checksum/source and do not disable antivirus or run as administrator.

Optional checks from PowerShell in the EXE folder:

```powershell
.\Codex-Swarm.exe --self-test   # offline TUI/state test, no Codex calls
.\Codex-Swarm.exe --doctor      # installed CLI/auth/model check, no inference
Get-FileHash .\Codex-Swarm.exe -Algorithm SHA256
```

Compare the hash with `SHA256SUMS.txt` from the same release.

## Setup for Windows

### 1. Download the repository

On GitHub select **Code -> Download ZIP**, extract it, and open the extracted folder.
Keep all the files together. You do not need to know the repository owner's username.

Or clone the URL from the repository's **Code** button and open the cloned folder.

### 2. Install the Python requirements

Double-click **`install_requirements.bat`**.

Or run from PowerShell in the repository folder:

```powershell
.\install_requirements.bat
```

The installer creates a local `.venv`, installs this project and its dependencies
from `requirements.txt` / `pyproject.toml`, then runs `pip check`. It does not install
Codex, sign you in, change PowerShell execution policy, or modify account credentials.
Run it again after updating the source. It is safe to reuse an existing compatible venv.

**Manual alternative:**

```powershell
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If the `py` launcher is unavailable, use `python` instead of `py -3`.

### 3. Install Codex and sign in

Follow the [official CLI installation guide](https://learn.chatgpt.com/docs/codex/cli).
If you already have Codex installed, check its version rather than reinstalling it.

```powershell
codex --version
codex login
codex login status
```

Choose **Sign in with ChatGPT** in the browser flow. This app rejects API-key-only
logins. The CLI owns authentication; never paste passwords or tokens into the app.
[Official authentication documentation](https://learn.chatgpt.com/docs/auth).

If PowerShell blocks an npm-installed `codex.ps1` wrapper, use `codex.cmd` for these
commands instead. Follow the official installer instructions if Codex is not on PATH.

### 4. Launch

Double-click **`run.bat`**, or run:

```powershell
.\run.bat
```

Direct Python also works without enabling PowerShell scripts:

```powershell
& .\.venv\Scripts\python.exe .\main.py
```

**Check installation/authentication without an inference call:**

```powershell
.\run.bat --doctor
```

The doctor prints the selected native CLI, login status, and model catalog. This
release was live-tested with CLI `0.162.0-alpha.2`; older CLI versions can reject
new model catalogs or required flags. If discovery is wrong, set `codex_binary`
to your native `codex.exe` in **Agent Configuration**.

## Setup for Linux

Install **Python 3.11+**, Git, and the official Codex CLI. On Debian/Ubuntu, ensure
Python's `venv` module is installed (for example, `sudo apt install python3-venv git`);
the app installer itself does not need root. Check `python3 --version` first: an
older distribution may need a newer Python version installed separately.

```sh
git clone https://github.com/94q/free-codex-swarm.git
cd free-codex-swarm
sh install_requirements.sh
codex login
codex login status
sh run.sh --doctor
sh run.sh
```

Use ChatGPT sign-in in the official CLI browser/device flow. On a remote/headless
machine follow the CLI's documented authentication options. Set `PYTHON=python3.13`
before running the installer if your default `python3` is too old. The script
creates `.venv` locally; no system-wide Python package installation is needed.

## Setup for macOS

Install **Python 3.11+** with pip/venv, Git, and the official Codex CLI. Both Intel
and Apple Silicon use this source setup (there is no macOS binary release).
Use the [Python macOS installer](https://www.python.org/downloads/macos/) or your
usual package manager. Git can come from Apple's Command Line Tools (`xcode-select --install`)
or your existing Git installation. The commands below run in Terminal:

```sh
git clone https://github.com/94q/free-codex-swarm.git
cd free-codex-swarm
sh install_requirements.sh
codex login
codex login status
sh run.sh --doctor
sh run.sh
```

For both POSIX platforms, launch from an interactive UTF-8 terminal. Terminal
window resizing is left to the host; enlarge it manually if needed. Native Codex
sandboxing remains enabled; Windows-only sandbox settings are not passed on POSIX.
The source test suite runs on Windows, Linux, and macOS in GitHub Actions; real
agent inference and graphical terminal presentation on Linux/macOS have not been
live-tested by the maintainer.

## Run your first task

1. Select **Projects** and add a Git repository that has at least one commit.
   Commit or stash your changes yourself first; the app refuses dirty projects.
2. Open **Agent Configuration**. Choose mode, concurrency, and invocation budget.
   **Read-only is the default.** For code changes, explicitly set `permission`
   to `workspace-write` and Apply.
3. Run `models` to inspect access and supported reasoning options for your login.
4. Select **Start New Task**, describe the objective, and Apply.
5. Watch the worker dashboard and inspect the report after the final review.
6. If the result is `ready`, run `promote <task-id>` and confirm with `PROMOTE`.
   Promotion is never automatic.

Example objective:

```text
Fix the failing arithmetic tests. Keep public function signatures unchanged,
limit changes to the arithmetic modules, and run the existing tests.
```

On Windows, sandbox defaults to `elevated`. If official sandbox setup fails, fix it
using the CLI's guidance. A supported `unelevated` fallback can be selected
explicitly in Agent Configuration, but has weaker isolation. There is no silent
fallback or automatic elevation. [Windows sandbox guide](https://learn.chatgpt.com/docs/windows/windows-sandbox).

## Accounts and process slots

The default is **one coordinator + three worker slots**. Blank `codex_home` values
share your current CLI login and allowance; more slots do not create new accounts.

To use an independently authenticated session:

1. Open **Account / Session Management -> Configure Worker Sessions**.
2. Give the profile a separate absolute `codex_home` directory.
3. Run `login session_02` (replace the ID with your profile's ID) and complete
   the official browser flow.

Use accounts you are authorized to access. The tool does not create accounts,
automatically rotate identities, pool quotas, or guarantee free/trial access.
Independent-account flows are implemented but were not live-tested with multiple
accounts. See the [full session guide](docs/USAGE.md#sessions-are-not-pooled-accounts).

## Commands and shortcuts

| Command | Purpose |
| --- | --- |
| `help`, `home` | Command reference / home menu |
| `new`, `projects` | New objective / select repository |
| `agents`, `status`, `logs [agent]` | Dashboard, status, and event logs |
| `models`, `accounts`, `slots <n>` | Catalog and session settings |
| `agent_config`, `settings` | Engine preferences / additional preferences |
| `theme`, `ascii`, `colors` | Interface customization |
| `save`, `back` | Save appearance / discard draft |
| `history`, `resume <id>`, `retry <id>` | Saved work and recovery |
| `review <id>`, `promote <id>` | Final review / confirmed integration |
| `stop <agent>`, `cancel`, `exit` | Stop a worker, cancel a task, or exit |
| `reset_settings` | Confirm a backed-up reset of all preferences |

**Arrow keys** navigate · **Enter** selects · **Ctrl+L** focuses the prompt ·
**Ctrl+N** starts a task · **Ctrl+Enter** applies the editor · **Esc** returns home.
Prompt **Up/Down** recall history and **Tab** completes commands. This is not an OS shell.

## Appearance and window sizing

Choose **Customize Interface** to preview/save any of the 16 palettes or import,
paste, and edit artwork. The default is the supplied cat; its signature is retained.

Classic PowerShell console windows request at least **120 columns x 44 rows** at
startup. Larger saved artwork raises the target, subject to display/font limits.
Windows Terminal and embedded terminals own their outer-window sizing. Artwork
remains scrollable if it cannot fit; `--no-resize` leaves the window unchanged.
[Detailed appearance guide](docs/USAGE.md#appearance).

## Troubleshooting

| Problem | What to do |
| --- | --- |
| Python not found | Install Python 3.11+, enable PATH/launcher, and reopen the terminal. |
| `Launch.ps1` is blocked | Use `run.bat` or direct Python; no execution-policy change is needed. |
| Missing Python module | Rerun `install_requirements.bat` and check its installation output. |
| Codex not found | Install the official CLI, reopen the terminal, or set native `codex_binary`. |
| API-key authentication rejected | Run `codex login` and choose ChatGPT sign-in. |
| Unknown model/effort or flag | Update the official CLI; run `--doctor` and `models`; do not hard-code unavailable models. |
| Dirty Git checkout | Review and commit/stash your changes yourself before starting. |
| Quota/model unavailable | Wait or adjust your authorized configuration; the app does not bypass limits. |
| Sandbox setup fails | Use official sandbox troubleshooting; fallback selection is manual. |
| Another instance owns state | Close the existing app; a stale lock filename alone does not mean the lock is held. |
| Artwork is partly hidden | Enlarge your terminal or scroll the artwork panel. |

State defaults:

- **Windows EXE:** `codex-swarm-data` beside the executable.
- **Windows source:** `%LOCALAPPDATA%\CodexSwarm` (legacy `CodexNexus` is reused).
- **Linux source:** `$XDG_DATA_HOME/CodexSwarm`, or `~/.local/share/CodexSwarm`.
- **macOS source:** `~/Library/Application Support/CodexSwarm`.

`--home` and `CODEX_SWARM_HOME` override these defaults. A reset backs up preferences and leaves
Codex authentication, task records, and preserved worktrees alone.

## Development

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m ruff check codex_swarm scripts tests --select F
```

Normal tests use mocked provider calls and temporary local Git/process fixtures;
they do not sign in or consume Codex allowance. GitHub Actions runs the Windows,
Linux, and macOS suite on Python 3.11 and 3.13. The live acceptance scripts are explicit opt-in and
consume your existing allowance; do not run them casually or in public CI.

[Building the EXE](docs/BUILDING.md) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md) ·
[Verification](VERIFICATION.md) · [Limitations](LIMITATIONS.md) ·
[Detailed usage](docs/USAGE.md)

## License and credits

Original project code and documentation are released under the [MIT License](LICENSE).
Third-party dependencies keep their own licenses. The supplied cat carries the
signature `ctr`; see [third-party notices](THIRD_PARTY_NOTICES.md) for its provenance
and licensing status. OpenAI, ChatGPT, and Codex names belong to their respective owners.
