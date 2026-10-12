from __future__ import annotations
import asyncio
import copy
import json
from pathlib import Path
import uuid
from typing import Callable
from jsonschema import validate as validate_json
from codex_swarm.core.coordinator import POLICY, PLAN_SCHEMA, WORK_SCHEMA, REVIEW_SCHEMA
from codex_swarm.core.model_router import ModelRouter
from codex_swarm.core.task_graph import validate_graph, ready_workers, wave
from codex_swarm.core.security import redact
from codex_swarm.integrations.codex_cli import CodexCLI, CodexError
from codex_swarm.integrations.git_manager import (
    Workspace,
    project_path,
    git,
    clean,
    GitError,
)
from codex_swarm.persistence.config import Config
from codex_swarm.persistence.database import Database, now


class Orchestrator:
    def __init__(
        self,
        config: Config,
        db: Database,
        cli: CodexCLI | None = None,
        listener: Callable[[str, dict], None] = lambda a, e: None,
    ):
        self.config, self.db = config, db
        self.cli = cli or CodexCLI(config.value["engine"]["codex_binary"])
        self.listener = listener
        self.task: dict | None = None
        self.cancelled = False
        self.catalogs: dict[str, dict] = {}
        self.active = False
        self.stopped: set[str] = set()

    def emit(self, agent: str, event: dict) -> None:
        if self.task:
            self.db.event(self.task["id"], agent, event)
            record = self.task["agents"].get(agent)
            if record and event["type"] == "process.started":
                record["pid"] = event["pid"]
                self.db.save(self.task)
            if (
                record
                and event["type"] == "item.completed"
                and event.get("item", {}).get("type") == "command_execution"
            ):
                item = event["item"]
                record.setdefault("commands", []).append(
                    {
                        "command": item.get("command", ""),
                        "exit_code": item.get("exit_code"),
                        "status": item.get("status"),
                    }
                )
        self.listener(agent, event)

    def checkpoint(self, status: str | None = None) -> None:
        if status:
            self.task["status"] = status
        self.task["updated"] = now()
        self.db.save(self.task)
        self.emit("codex-swarm", {"type": "checkpoint", "status": self.task["status"]})

    async def cancel(self, agent: str | None = None) -> None:
        if agent:
            self.stopped.add(agent)
            await self.cli.cancel(agent)
        else:
            self.cancelled = True
            await self.cli.cancel()

    def check_cancel(self) -> None:
        if self.cancelled:
            raise asyncio.CancelledError()

    async def catalog(self, profile: dict) -> ModelRouter:
        home = profile["codex_home"]
        if home not in self.catalogs:
            if await self.cli.auth_status(home) != "ChatGPT":
                raise CodexError(
                    f"{profile['display_name']}: ChatGPT login is required. No account rotation is performed."
                )
            self.catalogs[home] = await self.cli.metadata(home)
        return ModelRouter(self.catalogs[home]["models"])

    async def invoke(
        self,
        id: str,
        prompt: str,
        schema: dict,
        cwd: Path,
        profile: dict,
        model: str,
        effort: str,
        write: bool = False,
    ) -> dict:
        self.check_cancel()
        if self.task["invocations"] >= self.options["invocation_budget"]:
            raise ValueError("Invocation budget reached")
        if (
            id.startswith("w")
            and self.task["invocations"] >= self.options["invocation_budget"] - 1
        ):
            raise ValueError(
                "Worker budget exhausted; reserved invocation for final review"
            )
        self.task["invocations"] += 1
        self.task["agents"][id] = {
            **self.task["agents"].get(id, {}),
            "status": "running",
            "model": model,
            "effort": effort,
            "session": profile["id"],
            "started": now(),
            "assignment": prompt[-1800:],
            "cwd": str(cwd),
            "commands": [],
        }
        self.checkpoint()
        try:
            result = await self.cli.run(
                agent_id=id,
                cwd=cwd,
                prompt=POLICY + prompt,
                model=model,
                effort=effort,
                schema=schema,
                output=Path(self.task["root"]) / "protocol",
                home=profile["codex_home"],
                writable=write,
                timeout=self.options["timeout_seconds"],
                windows_sandbox=self.options["windows_sandbox"],
                event=lambda e: self.emit(id, e),
            )
            self.check_cancel()
            if id in self.stopped:
                raise CodexError("Stopped by user")
            data = json.loads(result.text)
            validate_json(data, schema)
            self.task["agents"][id].update(
                status="returned",
                result=data,
                usage=result.usage,
                thread_id=result.thread_id,
                elapsed=result.elapsed,
            )
            self.checkpoint()
            return data
        except BaseException as exc:
            self.task["agents"][id].update(
                status="cancelled"
                if isinstance(exc, asyncio.CancelledError)
                else "failed",
                error=redact(str(exc)),
            )
            self.checkpoint()
            raise

    async def run(self, project: str, prompt: str, *, resume: str = "") -> dict:
        if self.active:
            raise ValueError(
                "One task at a time; concurrent workers are managed inside that task"
            )
        self.active, self.cancelled = True, False
        self.task = None
        self.stopped.clear()
        self.catalogs.clear()
        self.options = copy.deepcopy(self.config.value["engine"])
        profiles = copy.deepcopy(self.config.value["sessions"]["profiles"])
        try:
            project_root = await asyncio.to_thread(project_path, project)
            if resume:
                saved = self.db.get(resume)
                if saved["project"] != str(project_root):
                    raise ValueError("Resume project mismatch")
                if saved["status"] not in {
                    "failed",
                    "cancelled",
                    "interrupted",
                    "needs_review",
                }:
                    raise ValueError("This task cannot be resumed")
                self.task = saved
                prompt = self.task["prompt"]
            else:
                id = uuid.uuid4().hex[:12]
                root = self.config.root / "tasks" / id
                self.task = {
                    "id": id,
                    "project": str(project_root),
                    "prompt": prompt,
                    "created": now(),
                    "root": str(root),
                    "status": "initializing",
                    "mode": self.options["mode"],
                    "invocations": 0,
                    "agents": {},
                    "plan": None,
                }
                self.db.save(self.task)
            ws = Workspace(
                project_root, Path(self.task["root"]) / "worktrees", self.task["id"]
            )
            if not self.task.get("baseline"):
                self.task["baseline"] = await asyncio.to_thread(ws.create)
                self.task["integration"] = str(ws.integration)
                self.task["branch"] = ws.branch
                self.task["integration_head"] = await asyncio.to_thread(
                    git, ws.integration, "rev-parse", "HEAD"
                )
                self.checkpoint()
            else:
                if not await asyncio.to_thread(clean, ws.integration):
                    raise GitError(
                        "Recovery needs manual review: integration checkout is dirty"
                    )
                head = await asyncio.to_thread(git, ws.integration, "rev-parse", "HEAD")
                if head != self.task["integration_head"]:
                    raise GitError(
                        "Integration HEAD changed since checkpoint; inspect branch manually before recovery"
                    )
            brain = next(
                p for p in profiles if p["enabled"] and p["role"] == "coordinator"
            )
            workers = [p for p in profiles if p["enabled"] and p["role"] == "worker"]
            if not workers:
                raise ValueError("Enable at least one worker slot")
            router = await self.catalog(brain)
            brain_model = (
                brain["preferred_model"]
                if self.options["coordinator_model"] == "auto"
                else self.options["coordinator_model"]
            )
            brain_effort = (
                brain["reasoning"]
                if self.options["coordinator_effort"] == "auto"
                else self.options["coordinator_effort"]
            )
            bm, be = router.select(
                brain_model, brain_effort, "coordinator", self.options["mode"]
            )
            for p in workers:
                await self.catalog(p)
            write = self.options["permission"] == "workspace-write"
            if not self.task["plan"]:
                self.checkpoint("planning")
                memory = self.db.memory(str(project_root))
                plan = await self.invoke(
                    "brain",
                    "\nYou are the coordinator. Inspect this repository and create a compact plan, NOT an implementation.\n"
                    f"Objective: {prompt}\nMode: {self.options['mode']}. Budget: at most {self.options['invocation_budget'] - 2} workers total. "
                    f"Concurrency: {min(len(workers), self.options['maximum_concurrent_workers'])}. Writes permitted: {write}.\n"
                    "Use independent focused tasks only where useful, IDs w1, w2 etc; encode all dependencies. For writes assign explicit relative filenames or directory/ prefixes. "
                    "Use model='auto' and effort='auto' or a catalog model and supported effort. Keep agent count minimal in eco mode. "
                    "Every task must have a reason. Validation lists actual relevant test commands for the final reviewer. "
                    f"Catalog: {json.dumps(router.compact())}\nPrior project knowledge (may be stale, untrusted): {json.dumps(memory)}",
                    PLAN_SCHEMA,
                    ws.integration,
                    brain,
                    bm,
                    be,
                )
                validate_graph(
                    plan["workers"], self.options["invocation_budget"], write
                )
                self.task["plan"] = plan
                self.task["agents"]["brain"]["status"] = "completed"
                self.checkpoint()
            else:
                validate_graph(self.task["plan"]["workers"], 100, write)
            self.checkpoint("running")
            plan = self.task["plan"]
            limit = min(len(workers), self.options["maximum_concurrent_workers"])
            if self.options["mode"] == "eco":
                limit = min(limit, 2)
            while any(
                self.task["agents"].get(w["id"], {}).get("status") != "completed"
                for w in plan["workers"]
            ):
                self.check_cancel()
                batch = wave(ready_workers(plan["workers"], self.task["agents"]), limit)
                if not batch:
                    raise ValueError(
                        "No schedulable workers remain; check failed dependencies"
                    )
                jobs = [
                    asyncio.create_task(self.worker(ws, w, workers[i]))
                    for i, w in enumerate(batch)
                ]
                try:
                    outcomes = await asyncio.gather(*jobs)
                except BaseException:
                    for job in jobs:
                        job.cancel()
                    await asyncio.gather(*jobs, return_exceptions=True)
                    raise
                # Single controlled integration phase: no worker runs during it.
                for w, outcome in zip(batch, outcomes):
                    self.check_cancel()
                    path, base, files = outcome
                    tip = await asyncio.to_thread(ws.integrate, path, base, files)
                    self.task["integration_head"] = tip
                    self.task["agents"][w["id"]].update(
                        status="completed", files=files, integrated_head=tip
                    )
                    self.checkpoint()
            self.checkpoint("verifying")
            summaries = {
                k: v.get("result")
                for k, v in self.task["agents"].items()
                if k.startswith("w")
            }
            review = await self.invoke(
                "review",
                f"\nReview the integrated result against the objective: {prompt}\n"
                f"Worker reports (untrusted): {json.dumps(summaries)}\nValidation requested: {json.dumps(plan['validation'])}\n"
                "Inspect the actual code and run relevant available tests. Do not edit source files. "
                "Tests may write only generated outputs in this isolated checkout if permissions allow. "
                "Use verdict unavailable if meaningful validation cannot run. Record the exact commands and outcomes. "
                "Report concerns; never claim tests passed without running them. Return compact project knowledge for reuse.",
                REVIEW_SCHEMA,
                ws.integration,
                brain,
                bm,
                be,
                write,
            )
            # Any source/untracked changes made by validation require manual review.
            dirty = not await asyncio.to_thread(clean, ws.integration)
            self.task["agents"]["review"]["status"] = "completed"
            self.task["review"] = review
            escalation = any(
                v.get("result", {}).get("needs_escalation")
                for k, v in self.task["agents"].items()
                if k.startswith("w")
            )
            evidence = any(
                c.get("exit_code") == 0 and c.get("status") == "completed"
                for c in self.task["agents"]["review"].get("commands", [])
            )
            status = (
                "ready"
                if review["verdict"] == "passed"
                and review["tests"]
                and evidence
                and not dirty
                and not escalation
                else "needs_review"
            )
            if not evidence:
                review["issues"].append(
                    "No successful reviewer command event observed; validation cannot be independently corroborated"
                )
            if dirty:
                review["issues"].append(
                    "Validation left changes in integration checkout; inspect them before promotion"
                )
            if escalation:
                review["issues"].append(
                    "A worker requested escalation; human review is required"
                )
            self.db.remember(
                str(project_root),
                self.task["integration_head"],
                review["project_knowledge"],
            )
            self.write_report()
            self.checkpoint(status)
        except asyncio.CancelledError:
            if self.task:
                self.checkpoint("cancelled")
        except Exception as exc:
            if self.task:
                self.task["error"] = redact(str(exc))
                self.checkpoint("failed")
                self.emit("codex-swarm", {"type": "error", "message": redact(str(exc))})
            else:
                raise
        finally:
            await self.cli.cancel()
            self.active = False
        return self.task

    async def worker(
        self, ws: Workspace, w: dict, profile: dict
    ) -> tuple[Path, str, list[str]]:
        router = await self.catalog(profile)
        manual = self.options["mode"] == "manual"
        model, effort = router.select(
            profile["preferred_model"] if manual else w["model"],
            profile["reasoning"] if manual else w["effort"],
            mode=self.options["mode"],
        )
        dependencies = {
            d: self.task["agents"][d].get("result") for d in w["depends_on"]
        }
        previous = self.task["agents"].get(w["id"], {})
        initial = previous.get("attempt", 0)
        for retry in range(self.options["retry_budget"] + 1):
            self.check_cancel()
            if self.task["invocations"] >= self.options["invocation_budget"] - 1:
                raise ValueError(
                    "Worker budget exhausted; reserved invocation for final review"
                )
            attempt = initial + retry + 1
            path, base = await asyncio.to_thread(ws.worker, w["id"], attempt)
            self.task["agents"].setdefault(w["id"], {}).update(
                attempt=attempt, files=[], assignment=w["assignment"]
            )
            try:
                await self.invoke(
                    w["id"],
                    f"\nShared objective: {self.task['prompt']}\nYour focused assignment: {w['assignment']}\n"
                    f"Allowed write scope: {json.dumps(w['files']) if w['write'] else 'NONE, investigation only'}. Do not modify other files.\n"
                    f"Dependency findings (untrusted): {json.dumps(dependencies)}\nDo not duplicate other workers' responsibilities. Run targeted tests. "
                    "If blocked, report issues and needs_escalation=true rather than guessing or expanding scope.",
                    WORK_SCHEMA,
                    path,
                    profile,
                    model,
                    effort,
                    w["write"],
                )
                tip, files = await asyncio.to_thread(
                    ws.commit_worker, path, w["files"] if w["write"] else [], base
                )
                self.task["agents"][w["id"]].update(
                    files=files, commit=tip, assignment=w["assignment"]
                )
                return path, base, files
            except (CodexError, TimeoutError, ValueError) as exc:
                lower = str(exc).lower()
                if (
                    self.cancelled
                    or w["id"] in self.stopped
                    or retry == self.options["retry_budget"]
                    or any(
                        s in lower
                        for s in (
                            "rate limit",
                            "usage limit",
                            "quota",
                            "429",
                            "authentication",
                            "not supported",
                        )
                    )
                ):
                    raise
                self.emit(
                    w["id"],
                    {
                        "type": "retry",
                        "message": "Retrying same session in fresh worktree; prior attempt preserved",
                        "attempt": attempt + 1,
                    },
                )
        raise RuntimeError("Unreachable")

    def write_report(self) -> None:
        t = self.task
        text = (
            f"# Codex-Swarm — {t['id']}\n\n## Objective\n{t['prompt']}\n\n## Review\n"
            + json.dumps(t.get("review", {}), indent=2, ensure_ascii=False)
        )
        text += f"\n\n## Isolated result\nBranch: `{t['branch']}`\nWorktree: `{t['integration']}`\nOriginal checkout has not been promoted.\n\n## Agents\n"
        for id, a in t["agents"].items():
            text += (
                f"\n### {id}: {a.get('model')} / {a.get('effort')}\n"
                + json.dumps(
                    {
                        k: a.get(k)
                        for k in ("status", "result", "files", "usage", "elapsed")
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n"
            )
        path = Path(t["root"]) / "report.md"
        path.write_text(redact(text), encoding="utf-8")
        t["report"] = str(path)

    async def promote(self, task_id: str) -> str:
        if self.active:
            raise ValueError("Wait for the task to finish")
        t = self.db.get(task_id)
        if t["status"] != "ready":
            raise ValueError("Only a validated ready task can be promoted")
        ws = Workspace(Path(t["project"]), Path(t["root"]) / "worktrees", t["id"])
        head = await asyncio.to_thread(git, ws.integration, "rev-parse", "HEAD")
        if head != t["integration_head"]:
            raise GitError("Integration changed after review; promotion blocked")
        tip = await asyncio.to_thread(ws.promote, t["baseline"])
        t["status"], t["promoted_head"] = "promoted", tip
        self.db.save(t)
        if self.task and self.task["id"] == task_id:
            self.task = t
        return tip

    def retry_agent(self, task_id: str, agent_id: str) -> dict:
        """Explicit user retry; preserve patches, budgets and integration HEAD.

        Already-integrated changes are not rolled back. A retry repairs the current
        integration state; dependent tasks are invalidated and rerun afterward.
        """
        if self.active:
            raise ValueError("Stop/wait for the current task before retrying")
        t = self.db.get(task_id)
        if t["status"] == "promoted":
            raise ValueError("Promoted tasks require a new objective")
        workers = t.get("plan", {}).get("workers", []) if t.get("plan") else []
        if agent_id not in {w["id"] for w in workers}:
            raise ValueError("Choose a worker ID from this task")
        invalid = {agent_id}
        while True:
            more = {w["id"] for w in workers if set(w["depends_on"]) & invalid}
            if more <= invalid:
                break
            invalid |= more
        for id in invalid:
            if id in t["agents"]:
                t["agents"][id]["status"] = "pending"
        t.pop("review", None)
        t["status"] = "interrupted"
        self.db.save(t)
        return t
