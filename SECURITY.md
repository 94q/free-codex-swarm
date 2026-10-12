# Security

This is an early release, not a certified hostile-code containment system.
Only run projects you trust within the selected official Codex sandbox.
Git worktrees isolate edits but are not an OS security boundary.

## Reporting a vulnerability

Do not publish credentials or exploitable details in an ordinary public issue.
Use GitHub's private vulnerability reporting feature when the repository owner
has enabled it. If unavailable, ask the maintainer for a private reporting channel
without disclosing the vulnerability publicly. Never send auth caches or tokens.

## Sensitive data

Never commit `.codex/auth.json`, environment secrets, local settings, task logs,
worktrees, or history databases. Redaction is best-effort, not a guarantee.
Authentication is handled by the official CLI; session credential homes are not
shared by this repository. See LIMITATIONS.md for sandbox and integration boundaries.

Maintainers should enable private vulnerability reporting and GitHub secret scanning
where available, and review reports before distributing updates.
