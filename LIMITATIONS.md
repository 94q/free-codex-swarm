# Release limitations and trust boundaries

This is a working, tested 0.2.0 implementation; it is **not a fully audited production-security product** and does not meet every aspirational requirement without qualification.

## Verified environmental blockers

1. The npm `codex` wrapper reported **0.135.0**. That executable could not parse the current catalog's `max` reasoning effort and rejected the selected current model. A separately installed native Codex app executable reported **0.162.0-alpha.2** and supported discovery and inference. Codex-Swarm now compares installed native versions; `--doctor` identifies the exact choice. Do not assume the npm wrapper and selected native executable are the same version.
2. The newer executable's **elevated sandbox** failed setup refresh because a runtime file was locked (`os error 32`). The supported **unelevated restricted-token** implementation successfully ran the live tests. Defaults retain elevated mode; selecting the weaker fallback is an explicit user decision. Codex-Swarm does not repair system ACLs, close other applications, or elevate itself.
3. PowerShell shell-snapshot warnings were emitted by Codex. Commands nevertheless executed successfully with the tested fallback.

## Intentionally conservative behavior

- Git repositories must have an initial commit and a clean working tree, including untracked files. Codex-Swarm refuses dirty projects instead of copying/stashing user changes. Non-Git projects, submodules, LFS/custom checkout filters require manual preparation.
- Integration conflicts, out-of-scope changes, deletions and symlink edits require manual review. Conflict detection and preservation work; **automatic semantic conflict repair is not implemented**.
- Automatic escalation to a stronger model is not implemented. Workers can request escalation; the result is held for review. Users can change explicit model preferences and retry. Retry budgets are bounded; rate-limit/auth failures do not rotate accounts.
- Execution strategy is the one implemented path: isolated CLI worktrees and serialized integration. There is no alternate native-subagent executor or interactive app-server approval bridge.
- `-a never` means operations requiring extra approval are refused, not granted silently. New permissions require user configuration outside the model. UI confirmation protects promotion, cancellation and sign-out, but Codex-Swarm is not a per-command security approval engine.
- Managed runs ignore ordinary user CLI configuration and local `.rules` files so Codex-Swarm owns their provider, sandbox and approval settings; applicable `AGENTS.md` files are still read. Do not rely on personal `.rules` as an additional security layer for Codex-Swarm. Organization-managed requirements remain CLI-enforced.
- Source changes made while final tests run cause `needs_review` if they leave a dirty worktree. Test output directories should be covered by the project's existing ignore rules; Codex-Swarm does not invent ignore rules to hide changes.
- Resume is a **Codex-Swarm checkpoint** mechanism, not an exact continuation of every CLI conversation. CLI thread IDs are retained for diagnostics. Completed workers are reused; unfinished attempts start fresh.
- Deleting session preferences does not delete official Codex authentication. Sign out explicitly when required.

## Authentication and availability

- Only the existing ChatGPT-authenticated account was live-tested. Separate credential homes and configurable slots are implemented, but multiple independently authenticated accounts were **not** created or verified.
- A session slot, Codex process, account identity and subagent are different concepts. Slots sharing one `CODEX_HOME` use one authentication state. No account pooling or quota multiplication is promised.
- Availability is validated against the CLI catalog and ultimately by inference. Catalog entries can be cached or unavailable to a particular account. Failures are shown, not replaced with invented success or paid API fallback.
- No exact allowance prediction is available. API-reported percentages/windows and per-turn token telemetry are displayed only when actually supplied.

## Security scope

- Git worktrees isolate edits; they are **not a hostile-code security boundary**. The official Codex OS sandbox is the execution boundary. Its implementation and enterprise policies remain important.
- All repository instructions, worker findings and memory are potentially untrusted. A higher-priority developer policy and CLI sandbox constrain execution; scope/path checks constrain integration. Prompt-injection resistance is not a formal guarantee.
- Repository tests run code. Only run projects you trust sufficiently for the configured official sandbox. `unelevated` has weaker network isolation than `elevated` and lacks denied-read-path support; no stronger guarantee is implied.
- No credential files are read by Codex-Swarm, and common token/password patterns are redacted from logs. Pattern-based redaction cannot identify every possible secret present in arbitrary project output. Treat local history/reports as private; do not enter secrets in prompts, configuration or command history.
- Native Git runs outside the agent sandbox for controlled worktree/integration operations. Hooks and external diff are disabled; filter-based checkouts are rejected. Existing Git/system configuration and concurrent external programs remain part of the host trust boundary.
- Job Objects are attached immediately after process creation; there is a small process-start race. Job Object and live cancellation tests passed, but this is not a certified hostile-process containment service.
- Only one instance per Codex-Swarm state directory is allowed. Independent state directories or external Git tools can still operate on the same repository; promotion rechecks cleanliness and HEAD but no distributed repository lock is implemented.

## UI / deployment scope

- Default artwork is the user-supplied cat. Terminal sizing is best-effort for classic Windows consoles, bounded by the current font/display. Other terminal hosts own their window size; oversized artwork stays scrollable without being replaced.
- Engine and session configuration use validated JSON forms inside the terminal, rather than separate graphical controls for every setting.
- Gradient borders apply to Rich boxed preview content. Textual's native scrollable widget borders use the selected solid border color.
- Live status comes from process/item events. It does not infer unobservable internal model progress. No fabricated percentage is displayed.
- Direct Roblox Studio interaction and production Roblox validation were not performed. Rojo/Luau tools can be used when present; sandbox/network limitations may require user action.
- Windows execution was tested on this host, including a real terminal launch and headless layouts at 120×45, 80×24 and 42×18. Other Windows versions/fonts/terminals are not certified. Linux/macOS source support and automated CI are included; real agent inference and native terminal presentation on those hosts have not been live-tested by the maintainer.
- Delivery includes Python source, platform launch scripts, an installable wheel, and a compressed standalone Windows x64 EXE. The EXE is unsigned and still requires external Git/Codex for agent tasks. Worktrees/logs have no automatic retention pruning. POSIX cancellation reaps process groups; Windows kill-on-close Job Objects have no equivalent crash-containment implementation here.
- The acceptance fixture is deliberately small. Passing it does not prove robustness on very large repositories, prolonged runs, complex merges or every third-party build system.
