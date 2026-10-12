# Detailed usage

## First task

1. Run `models` to inspect the actual model catalog and observed account usage.
2. Open **Projects**, add a **clean Git root with at least one commit**, and select it. The application does not automatically initialize repositories or stash user work.
3. Configure permission, mode, concurrency, invocation budget and timeout. Default: read-only, AUTO, 3 concurrent workers, 12 invocations, 1 retry, 900 seconds per invocation.
4. Choose **Start New Task** and enter a multiline objective. Apply authorizes the bounded Codex calls and selected sandbox permissions.
5. Inspect the live dashboard, worker rows and persisted event logs.
6. On completion, inspect the report and isolated integration branch. A `ready` result is eligible for `promote <task-id>`, which asks you to type `PROMOTE` before fast-forwarding the original checkout.


## Authentication and cost boundary

- Uses official `codex exec --json --output-schema` with existing ChatGPT CLI authentication; no API SDK/client, required API key, cookie scraping, credential copying, or token-file reads.
- Checks `codex login status` and rejects non-ChatGPT authentication. API-key environment variables are removed from child environments. The OpenAI provider and ChatGPT login method are explicitly selected for inference.
- Uses `app-server` JSON-RPC only for catalog / usage discovery. Model/effort pairs are validated against each selected session's catalog. A catalog entry is not proof of entitlement; a successful inference call verifies access.
- Actual calls consume your **existing ChatGPT/Codex allowance**. No allowance or concurrency guarantee is implied. Codex-Swarm does not purchase credits, reset limits, or rotate identities on quota errors.
- When usage telemetry is missing, it is marked unavailable. Real `turn.completed` token counts are retained per agent.

Architecture references: [non-interactive execution](https://learn.chatgpt.com/docs/non-interactive-mode), [app-server](https://learn.chatgpt.com/docs/app-server), [authentication](https://learn.chatgpt.com/docs/auth).

## Sessions are not pooled accounts

Four local process slots are configured initially: one coordinator and three workers. Two, three, four, five, eight, twelve, or more slots can be configured by increasing `maximum_slots`. Worker concurrency is an independent limit.

Each profile has an ID, display name, enabled state, role, model/effort preference and optional `codex_home`. **Blank `codex_home` means all those slots share the existing CLI login.** It does not mean separate identities or extra allowances.

For a genuinely separate login, set a new absolute `codex_home` directory in **Configure Worker Sessions**, then use `login session_02`. Official Codex opens its browser sign-in flow and owns all credentials. Codex-Swarm suppresses authentication process output so no token/device code is logged. If browser launch is unavailable, use official `codex login` interactively with the intended `CODEX_HOME`; do not paste credentials into Codex-Swarm.

`logout session_02` requires confirmation and signs out every slot sharing that credential home. Removing a profile removes only the preference: it deliberately does not erase its official Codex credentials or other session data. Independent-account authentication was not live-verified during this build.

## Execution model

- Coordinator runs at planning and final-review checkpoints, not on every status event.
- AUTO: coordinator chooses focused assignments and discovered model/effort pairs.
- ECO: favors efficient models, caps worker concurrency at two, asks for a minimal plan.
- PERFORMANCE: favors high reasoning where automatic effort selection is used.
- MANUAL: each assigned worker uses its profile's model/effort preference. The coordinator still creates the task graph.
- Native nested subagents are disabled so invocation/concurrency accounting remains under Codex-Swarm control; parallelism uses real independent CLI processes.
- Workers each get a fresh worktree, even for investigations. Dependency reports and integrated prerequisite changes are provided without repeating full exploration.
- Explicit overlapping file scopes are serialized. An entire worker wave completes before the single integration phase applies validated binary-safe patches.
- File-scope violations, deletion attempts, symlinks and patch conflicts stop integration and preserve work for manual review. No original working-tree changes are overwritten.
- Read-only tasks cannot acquire write permissions from their plan. Workspace-write is an explicit user setting.
- A final reviewer must provide a passing review, actual test descriptions and an observed successful command event. Any escalation, unavailable verification or dirty integration tree prevents automatic eligibility for promotion.
- Project summaries persist with their commit baseline, explicitly labeled as potentially stale context. Codex reads applicable `AGENTS.md` instructions.

## Command prompt

The persistent bottom prompt uses `username@fictional-ip:~$`. Username defaults to your Windows username. IP is randomly generated in the private `192.168.*.*` range and persisted, not queried from the network. Edit both with the `settings` command. Settings is command-only; the main menu has seven entries, ending with **7. Exit**.

| Command | Action |
|---|---|
| `help`, `home` | Command reference / main menu |
| `new`, `projects` | Objective editor / project selection |
| `agents`, `status` | Real live dashboard |
| `logs [agent]` | Persisted JSON events for current/selected task |
| `accounts`, `models` | Session settings / real catalog and usage |
| `mode [auto\|eco\|performance\|manual]` | Operating mode |
| `settings`, `agent_config` | Validated editable preferences |
| `slots <count>` | Resize process-slot configuration |
| `login <session>`, `logout <session>` | Official authentication / confirmed sign-out |
| `theme`, `ascii`, `colors` | Appearance customization |
| `save`, `back` | Save appearance draft / discard preview |
| `history` | Saved task records and report paths |
| `stop <agent>` | Stop one running process tree |
| `cancel` | Confirm whole-task cancellation |
| `resume <task>` | Continue unfinished checkpoints |
| `retry <task-or-worker>` | Resume task or explicitly rerun a worker |
| `review <task>` | Request another coordinator review |
| `promote <task>` | Confirm safe fast-forward into original checkout |
| `clear`, `exit` | Clear visible logs / safe exit |

Menu numbers work either as shortcuts in focused menus or as commands. Arrow keys navigate menus; Up/Down in the prompt recall saved command history; Tab completes commands. Ctrl+L focuses the prompt, Ctrl+N starts a task, Ctrl+Enter applies the editor, Esc returns home. The input never evaluates arbitrary OS commands.

## Appearance

- Black background, pale-green/white defaults, the user-supplied cat artwork, double borders. Page headings are centered independently of the artwork width.
- Sixteen built-in palettes plus named custom themes; HEX validation; draft preview with Apply/Save/Cancel/Reset. New choices: Amber Console, Ocean Depths, Rose Quartz, Tokyo Night, Dracula, Nord, Gruvbox, Catppuccin Mocha, Sunset Glow, and Mint Terminal.
- Import `.txt`/`.ans`, paste/edit multiline Unicode, choose built-ins, remove/restore artwork. UTF-8 with CP437 fallback; control sequences are stripped, whitespace retained.
- Four gradient directions, enable switch and banner/heading/compatible-box scope. Native widget borders remain a solid theme color.
- Startup requests at least **120 columns × 44 rows**, increased to the saved artwork's cell width plus 8 columns and line count plus 32 rows. Classic Windows PowerShell/Console windows are enlarged before the TUI starts, up to the current font/display limit. Already-larger windows are retained. `--no-resize` opts out.
- Windows Terminal, embedded terminals, SSH, and other hosts control their own outer-window size; no unrelated window is resized. If the display/host cannot fit larger artwork, the full artwork remains in a vertically/horizontally scrollable panel instead of being replaced or lost. [Windows console sizing reference](https://learn.microsoft.com/windows/console/setconsolewindowinfo).
- `NO_COLOR` is respected. If your terminal explicitly sets it, remove that environment setting if you want color. Use Windows Terminal with a Unicode monospace font.

## State, recovery and retained files

For a fresh set of preferences, enter `reset_settings` and confirm with `RESET`, or launch with `--reset-settings`. The old settings are backed up as `settings.before-reset-*.json`. All preferences, engine/session configuration, saved project selections, custom themes, and command history return to defaults. Official Codex authentication and historical task/worktree data are not deleted. A queued `reset-settings.request` applies on the next launch while holding the instance lock.

Default state: EXE uses `codex-swarm-data` beside itself; Windows source uses `%LOCALAPPDATA%\CodexSwarm`; Linux uses `$XDG_DATA_HOME/CodexSwarm` or `~/.local/share/CodexSwarm`; macOS uses `~/Library/Application Support/CodexSwarm`. Use `--home <path>` or `CODEX_SWARM_HOME` to choose another **Codex-Swarm state** directory (this is separate from credential `CODEX_HOME`).

Upgrading from the previous name preserves your settings and task history: an existing `%LOCALAPPDATA%\CodexNexus` directory is reused without moving it. The legacy `NEXUS_HOME` variable is also accepted; `CODEX_SWARM_HOME` takes precedence. Existing integration branches remain valid. Historical live-test records retain their original names and paths as evidence, not current branding.

- `settings.json`: validated, atomically replaced preferences; malformed originals are backed up on the next save.
- `history.sqlite3`: tasks, checkpoints, redacted event logs, project summaries, real token counts.
- `tasks/<id>/worktrees`: preserved coordinator integration tree and worker attempts.
- `tasks/<id>/report.md`: consolidated report after review.
- `instance.lock`: only one Codex-Swarm process may own a state directory. An OS-held file lock is automatically released on process exit or crash; PID metadata is diagnostic only.

Windows process Job Objects and process-tree termination are used for cancellation/crash containment. On restart, running records become `interrupted`. Resume skips completed/integrated workers, never automatically resets usage budgets, never rotates accounts, and refuses an unexpected integration HEAD or dirty integration checkout. Explicit worker retry reruns its dependent tasks but does not roll back previously integrated commits.

Worktrees are intentionally **not automatically deleted**. They preserve failed attempts and manual recovery evidence. Once finished, inspect `git worktree list` and remove only the worktrees you have reviewed and no longer need using Git. Do not delete a task directory while Git still registers its worktrees.

## Fresh installation / development

Requires Windows/Linux/macOS, Python 3.11+ for source (not needed for the Windows EXE), Git, an official Codex CLI compatible with your account/model catalog, and working official sandbox setup.

```powershell
py -3 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install -e '.[test]'
& .\.venv\Scripts\python.exe .\main.py --doctor
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe .\main.py
```

Codex-Swarm discovers native CLI executables on PATH and in the known npm/Codex app locations, compares their reported versions, and selects the newest installed executable. You can pin an exact `codex_binary` in Agent Configuration. It never installs or updates Codex automatically. `--doctor` prints the selected binary.

Headless runs use the saved settings and never promote automatically:

```powershell
& .\.venv\Scripts\python.exe .\main.py --project 'C:\Your\CleanGitRepo' --prompt 'Your development objective'
& .\.venv\Scripts\python.exe .\main.py --resume TASK_ID
```

The live acceptance scripts are opt-in and consume your ChatGPT allowance. They are not part of normal pytest execution. See their `--help` before running them. Unit tests use provider mocks; process and Git tests use real temporary subprocesses/repositories.