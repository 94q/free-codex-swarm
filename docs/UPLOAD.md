# Publish free-codex-swarm

The repository is published at https://github.com/94q/free-codex-swarm. This guide describes source updates; Windows executables belong in GitHub Releases, not the Git tree. See [BUILDING.md](BUILDING.md) for the tag-triggered release process.

## Before publishing

- Confirm permission to distribute the supplied `ctr` cat, or replace it with artwork you own. See THIRD_PARTY_NOTICES.md.
- Review the MIT copyright line and contributor attribution.
- Upload the contents of the clean `free-codex-swarm` source folder, not the ZIP file itself.
- Do not upload an installed `.venv`, local verification logs, settings, task/history databases, auth files, or private worktrees.

## GitHub web upload

1. Create a repository named `free-codex-swarm`.
2. If uploading these files, do not generate another README or license during creation.
3. Select **Add file -> Upload files** and upload the clean folder's contents at the repository root.
4. Ensure `README.md`, `LICENSE`, `.github`, `codex_swarm`, `scripts`, and `tests` are included.
5. Commit the upload. Confirm the README preview image and relative documentation links work.

## Git push

Open PowerShell inside the clean source folder:

```powershell
git init
git branch -M main
git add .
git status
git diff --cached --stat
git commit -m "initial codex-swarm release"
```

Copy the repository's HTTPS clone URL from GitHub, then set the remote and push:

```powershell
git remote add origin "PASTE_YOUR_REPOSITORY_HTTPS_URL_HERE"
git push -u origin main
```

Replace the quoted placeholder with your actual URL. Use GitHub's normal authentication flow.
If Git requests an author name/email, configure your own chosen identity before committing.

## Recommended repository settings

Description: `a terminal command center for running parallel codex agents with chatgpt sign-in.`

Suggested topics: `codex`, `chatgpt`, `multi-agent`, `terminal-ui`, `python`, `git-worktrees`, `windows`.

Enable private vulnerability reporting where available. The included Actions workflow runs
normal tests and builds a wheel; it never runs live Codex calls. Its first remote run
still needs to pass after upload. Add tested wheels/ZIPs as release attachments rather than
committing virtual environments or build output.
