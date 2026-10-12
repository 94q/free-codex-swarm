"""Explicit opt-in real Codex integration test. Uses the current ChatGPT allowance.
Run: python tests/live_verify.py --run --root ABSOLUTE_TEST_DIRECTORY
Creates only a new disposable fixture repository. Never touches a user's project.
"""

from __future__ import annotations
import argparse
import asyncio
import json
from pathlib import Path
import sys
import time
from codex_swarm.core.orchestrator import Orchestrator
from codex_swarm.persistence.config import Config
from codex_swarm.persistence.database import Database
from codex_swarm.integrations.git_manager import git


async def verify(root: Path, sandbox: str):
    root.mkdir(parents=True, exist_ok=False)
    repo = root / "fixture"
    repo.mkdir()
    git(repo, "init")
    (repo / "a.py").write_text("def add(a, b):\n    return a - b\n")
    (repo / "b.py").write_text("def mul(a, b):\n    return a + b\n")
    (repo / "test_math.py").write_text(
        "import unittest\nfrom a import add\nfrom b import mul\nclass MathTests(unittest.TestCase):\n    def test_add(self): self.assertEqual(add(2,3),5)\n    def test_mul(self): self.assertEqual(mul(2,3),6)\nif __name__=='__main__': unittest.main()\n"
    )
    (repo / ".gitignore").write_text("__pycache__/\n")
    git(repo, "add", ".")
    git(
        repo,
        "-c",
        "user.name=Swarm Test",
        "-c",
        "user.email=test@localhost",
        "commit",
        "-m",
        "disposable fixture",
    )
    c = Config(root / "state")
    c.value["engine"].update(
        permission="workspace-write",
        windows_sandbox=sandbox,
        invocation_budget=6,
        retry_budget=0,
        maximum_concurrent_workers=2,
        timeout_seconds=300,
    )
    c.save()
    db = Database(c.root)
    intervals = {}
    events = []

    def event(agent, e):
        events.append({"agent": agent, "time": time.monotonic(), **e})
        if e["type"] == "process.started":
            intervals.setdefault(agent, {})["start"] = time.monotonic()
        if e["type"] == "process.exited":
            intervals.setdefault(agent, {})["end"] = time.monotonic()
        print(
            agent,
            e["type"],
            str(e.get("message") or e.get("item", {}).get("command") or "")[:250],
            flush=True,
        )

    engine = Orchestrator(c, db, listener=event)
    t = await engine.run(
        str(repo),
        "Fix add in a.py and mul in b.py. For this concurrency acceptance test, assign exactly two independent writing workers, one per file, with no dependencies. Each should inspect its file then fix its arithmetic operator and validate its own function. Use an available efficient worker model with low reasoning. Final reviewer must run python -m unittest -v and verify both tests. Do not modify test_math.py. Keep the task minimal.",
    )
    w = [v for k, v in intervals.items() if k.startswith("w") and "end" in v]
    overlap = len(w) >= 2 and max(w[0]["start"], w[1]["start"]) < min(
        w[0]["end"], w[1]["end"]
    )
    original_unchanged = (
        "a - b" in (repo / "a.py").read_text()
        and "a + b" in (repo / "b.py").read_text()
    )
    result = {
        "task": t["id"],
        "status": t["status"],
        "error": t.get("error"),
        "real_worker_overlap": overlap,
        "intervals": intervals,
        "original_unchanged_before_promotion": original_unchanged,
        "report": t.get("report"),
    }
    if t["status"] == "ready":
        result["promoted_head"] = await engine.promote(t["id"])
        p = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "unittest",
            "-v",
            cwd=repo,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        out, _ = await p.communicate()
        result["independent_tests_exit"] = p.returncode
        result["independent_tests_output"] = out.decode()
    (root / "verification.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    (root / "events.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
    db.close()
    return (
        t["status"] == "ready"
        and overlap
        and original_unchanged
        and result.get("independent_tests_exit") == 0
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "--sandbox", choices=["elevated", "unelevated"], default="elevated"
    )
    args = parser.parse_args()
    if not args.run:
        parser.error("Explicit --run required; this test uses ChatGPT plan allowance")
    sys.exit(0 if asyncio.run(verify(args.root.resolve(), args.sandbox)) else 1)
