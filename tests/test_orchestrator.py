import asyncio
import json
import pytest
from codex_swarm.core.orchestrator import Orchestrator
from codex_swarm.integrations.codex_cli import Result, CodexError
from codex_swarm.persistence.config import Config
from codex_swarm.persistence.database import Database


class FakeCLI:
    def __init__(self, fail="", auth="ChatGPT"):
        self.processes = {}
        self.active = 0
        self.peak = 0
        self.calls = []
        self.fail = fail
        self.auth = auth

    async def auth_status(self, home=""):
        return self.auth

    async def metadata(self, home=""):
        return {
            "models": [
                {
                    "model": "test-model",
                    "defaultReasoningEffort": "low",
                    "supportedReasoningEfforts": [{"reasoningEffort": "low"}],
                    "isDefault": True,
                }
            ]
        }

    async def cancel(self, agent_id=None):
        pass

    async def run(self, **kw):
        id = kw["agent_id"]
        self.calls.append(id)
        self.active += 1
        self.peak = max(self.peak, self.active)
        kw["event"]({"type": "process.started", "pid": 123})
        try:
            await asyncio.sleep(0.06)
            if self.fail == id:
                raise CodexError("quota reached, 429")
            if id == "brain":
                data = {
                    "summary": "fix independently",
                    "workers": [
                        {
                            "id": f"w{i}",
                            "assignment": f"fix {f}",
                            "files": [f],
                            "depends_on": [],
                            "write": True,
                            "model": "auto",
                            "effort": "auto",
                            "reason": "independent file",
                        }
                        for i, f in enumerate(["a.py", "b.py"], 1)
                    ],
                    "validation": ["python -m unittest"],
                }
            elif id == "review":
                kw["event"](
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "mock validation",
                            "status": "completed",
                            "exit_code": 0,
                        },
                    }
                )
                data = {
                    "summary": "test-only fixture review",
                    "verdict": "passed",
                    "tests": ["mock validation"],
                    "issues": [],
                    "project_knowledge": "fixture",
                }
            else:
                f = "a.py" if id == "w1" else "b.py"
                (kw["cwd"] / f).write_text("fixed = True\n")
                data = {
                    "summary": "fixed",
                    "tests": [],
                    "issues": [],
                    "needs_escalation": False,
                }
            return Result(
                json.dumps(data), {"input_tokens": 1, "output_tokens": 1}, elapsed=0.06
            )
        finally:
            self.active -= 1


def setup(tmp_path, cli):
    c = Config(tmp_path / "state")
    c.value["engine"].update(permission="workspace-write", coordinator_effort="auto")
    c.save()
    db = Database(c.root)
    return Orchestrator(c, db, cli), db


async def test_parallel_and_history(repo, tmp_path):
    cli = FakeCLI()
    engine, db = setup(tmp_path, cli)
    t = await engine.run(str(repo), "fix")
    assert t["status"] == "ready", t.get("error")
    assert cli.peak == 2
    assert len(db.events(t["id"])) > 4
    assert db.get(t["id"])["agents"]["w1"]["files"] == ["a.py"]
    assert "a - b" in (repo / "a.py").read_text()
    db.close()


async def test_quota_no_rotation_or_retry(repo, tmp_path):
    cli = FakeCLI(fail="w1")
    engine, db = setup(tmp_path, cli)
    t = await engine.run(str(repo), "fix")
    assert t["status"] == "failed"
    assert cli.calls.count("w1") == 1
    db.close()


async def test_auth_block(repo, tmp_path):
    cli = FakeCLI(auth="Not authenticated")
    engine, db = setup(tmp_path, cli)
    t = await engine.run(str(repo), "fix")
    assert t["status"] == "failed"
    assert not cli.calls
    db.close()


async def test_cancel(repo, tmp_path):
    cli = FakeCLI()
    engine, db = setup(tmp_path, cli)
    job = asyncio.create_task(engine.run(str(repo), "fix"))
    while not cli.calls:
        await asyncio.sleep(0.01)
    await engine.cancel()
    t = await job
    assert t["status"] == "cancelled"
    db.close()


async def test_resume_uses_checkpoints(repo, tmp_path):
    cli = FakeCLI(fail="review")
    engine, db = setup(tmp_path, cli)
    t = await engine.run(str(repo), "fix")
    assert t["status"] == "failed"
    cli.fail = ""
    before = list(cli.calls)
    t = await engine.run(str(repo), "fix", resume=t["id"])
    assert t["status"] == "ready"
    assert cli.calls[len(before) :] == ["review"]
    db.close()


async def test_concurrency_limit(repo, tmp_path):
    cli = FakeCLI()
    engine, db = setup(tmp_path, cli)
    engine.config.value["engine"]["maximum_concurrent_workers"] = 1
    t = await engine.run(str(repo), "fix")
    assert t["status"] == "ready"
    assert cli.peak == 1
    db.close()


def test_recovery(tmp_path):
    db = Database(tmp_path)
    db.save({"id": "x", "status": "running", "agents": {"w1": {"status": "running"}}})
    assert db.recover() == 1
    assert db.get("x")["status"] == "interrupted"
    db.close()


async def test_invalid_new_project_does_not_corrupt_old_task(repo, tmp_path):
    cli = FakeCLI()
    engine, db = setup(tmp_path, cli)
    t = await engine.run(str(repo), "fix")
    id = t["id"]
    with pytest.raises(FileNotFoundError):
        await engine.run(str(tmp_path / "missing"), "next")
    assert db.get(id)["status"] == "ready"
    db.close()


async def test_retry_individual_worker(repo, tmp_path):
    cli = FakeCLI()
    engine, db = setup(tmp_path, cli)
    t = await engine.run(str(repo), "fix")
    engine.retry_agent(t["id"], "w1")
    before = len(cli.calls)
    t = await engine.run(str(repo), "fix", resume=t["id"])
    assert t["status"] == "ready"
    assert cli.calls[before:] == ["w1", "review"]
    db.close()
