"""Only Codex-Swarm branches/worktrees are changed automatically. No resets, cleans or force deletes."""

from __future__ import annotations
import os
from pathlib import Path
import subprocess
from codex_swarm.core.security import redact


class GitError(RuntimeError):
    pass


def git(path: Path, *args: str, check: bool = True) -> str:
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("GIT_"):
            env.pop(key)
    env["GIT_TERMINAL_PROMPT"] = "0"
    p = subprocess.run(
        [
            "git",
            "-c",
            "core.hooksPath=NUL" if os.name == "nt" else "core.hooksPath=/dev/null",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.fsmonitor=false",
            "-c",
            "diff.external=",
            "-C",
            str(path),
            *args,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=90,
        env=env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if p.returncode and check:
        raise GitError(redact(p.stderr.decode("utf-8", "replace")))
    return p.stdout.decode("utf-8", "replace").strip()


def project_path(path: str) -> Path:
    p = Path(path).expanduser().resolve(strict=True)
    if not p.is_dir() or p == Path(p.anchor):
        raise GitError("Select a project directory, not a drive root")
    top = Path(git(p, "rev-parse", "--show-toplevel")).resolve()
    if top != p:
        raise GitError(f"Select repository root: {top}")
    git(p, "rev-parse", "HEAD")
    if (p / ".gitmodules").exists():
        raise GitError(
            "Submodule repositories require manual preparation; Codex-Swarm will not initialize them"
        )
    # Checkout filters can execute programs on the host, outside the agent sandbox.
    # Reject filtered repositories rather than silently running them on worktree add.
    tracked = git(p, "ls-files", "-z").split("\x00")
    if tracked and tracked != [""]:
        for start in range(0, len(tracked), 100):
            chunk = [f for f in tracked[start : start + 100] if f]
            if not chunk:
                continue
            attrs = git(p, "check-attr", "filter", "--", *chunk)
            if any(
                line
                and not line.endswith(": unspecified")
                and not line.endswith(": unset")
                for line in attrs.splitlines()
            ):
                raise GitError(
                    "Git checkout/clean filters (including LFS) need manual preparation; no filtered worktree is created"
                )
    return p


def clean(path: Path) -> bool:
    return not git(path, "status", "--porcelain=v1", "--untracked-files=all")


def valid_scope(scope: str) -> bool:
    return (
        bool(scope)
        and not scope.startswith(("/", "\\", "-"))
        and ":" not in scope
        and "\\" not in scope
        and all(x not in {"..", ".git", ""} for x in scope.rstrip("/").split("/"))
        and not any(c in scope for c in "*?[]\x00\n")
    )


def in_scope(file: str, scopes: list[str]) -> bool:
    return any(file == s or (s.endswith("/") and file.startswith(s)) for s in scopes)


class Workspace:
    def __init__(self, project: Path, root: Path, task_id: str):
        self.project, self.root, self.task_id = project, root.resolve(), task_id
        self.root.mkdir(parents=True, exist_ok=True)
        self.integration = self.root / "integration"
        self.branch = f"codex-swarm/{task_id}/integration"
        # Saved pre-rename runs keep their existing integration branch.
        if self.integration.exists():
            existing = git(self.integration, "branch", "--show-current")
            if existing == f"nexus/{task_id}/integration":
                self.branch = existing

    def create(self) -> str:
        if not clean(self.project):
            raise GitError(
                "Project has uncommitted or untracked changes. Commit/stash them yourself before running; Codex-Swarm never touches them."
            )
        baseline = git(self.project, "rev-parse", "HEAD")
        git(
            self.project,
            "worktree",
            "add",
            "-b",
            self.branch,
            str(self.integration),
            baseline,
        )
        return baseline

    def worker(self, agent_id: str, attempt: int) -> tuple[Path, str]:
        path = self.root / f"{agent_id}-{attempt}"
        if path.exists():
            raise GitError(f"Preserved worktree already exists: {path}")
        base = git(self.integration, "rev-parse", "HEAD")
        git(self.project, "worktree", "add", "--detach", str(path), base)
        return path, base

    def commit_worker(
        self, path: Path, scopes: list[str], base: str
    ) -> tuple[str, list[str]]:
        # Guard against agent commits and include staged/untracked changes.
        changed = git(path, "diff", "--name-only", "-z", base).split("\x00")
        untracked = git(path, "ls-files", "--others", "--exclude-standard", "-z").split(
            "\x00"
        )
        files = sorted(set(f for f in changed + untracked if f))
        for f in files:
            if not valid_scope(f) or not in_scope(f, scopes):
                raise GitError(f"Out-of-scope edit blocked: {f}")
            target = path / f
            if not target.exists():
                raise GitError(
                    f"File deletion requires manual review: {f}; original checkout preserved"
                )
            if target.is_symlink() or not target.resolve().is_relative_to(
                path.resolve()
            ):
                raise GitError(f"Symlink/escaped edit blocked: {f}")
        if files:
            attrs = git(path, "check-attr", "filter", "--", *files)
            if any(
                line
                and not line.endswith(": unspecified")
                and not line.endswith(": unset")
                for line in attrs.splitlines()
            ):
                raise GitError(
                    "Custom Git clean filters are not run outside the agent sandbox"
                )
        if not files:
            return "", []
        # Do not stage ignored files, credentials or arbitrary directory trees.
        git(path, "add", "--", *files)
        if git(path, "diff", "--cached", "--name-only"):
            git(
                path,
                "-c",
                "user.name=Codex-Swarm",
                "-c",
                "user.email=codex-swarm@localhost",
                "commit",
                "-m",
                f"Codex-Swarm {self.task_id}: {path.name}",
            )
        # Support agent-authored commits by squash-applying the complete base delta.
        tip = git(path, "rev-parse", "HEAD")
        return tip, files

    def integrate(self, path: Path, base: str, files: list[str]) -> str:
        if not files:
            return git(self.integration, "rev-parse", "HEAD")
        patch = self.root / (path.name + ".patch")
        # Binary-safe patch; --output avoids shell redirection encoding corruption.
        git(
            path,
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--binary",
            "--full-index",
            f"--output={patch}",
            base,
            "HEAD",
            "--",
            *files,
        )
        try:
            git(self.integration, "apply", "--check", "--index", str(patch))
        except GitError as exc:
            raise GitError(
                f"Integration conflict. Original checkout untouched; inspect {patch}. {exc}"
            ) from exc
        git(self.integration, "apply", "--index", str(patch))
        git(
            self.integration,
            "-c",
            "user.name=Codex-Swarm",
            "-c",
            "user.email=codex-swarm@localhost",
            "commit",
            "-m",
            f"Integrate {path.name}",
        )
        return git(self.integration, "rev-parse", "HEAD")

    def promote(self, baseline: str) -> str:
        if not clean(self.project):
            raise GitError("Original checkout is dirty; refusing promotion")
        if git(self.project, "rev-parse", "HEAD") != baseline:
            raise GitError(
                "Original HEAD changed; review/merge the Codex-Swarm branch manually"
            )
        if not clean(self.integration):
            raise GitError("Integration worktree is dirty; inspect it before promotion")
        git(self.project, "merge", "--ff-only", self.branch)
        return git(self.project, "rev-parse", "HEAD")
