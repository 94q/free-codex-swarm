"""Opt-in live cancellation test against an existing disposable Git fixture."""

import argparse
import asyncio
import json
from pathlib import Path
import psutil
from codex_swarm.integrations.codex_cli import CodexCLI, CodexError
from codex_swarm.core.coordinator import obj, STR


async def main(repo: Path, output: Path):
    cli = CodexCLI()
    started = asyncio.Event()
    events = []

    def event(e):
        events.append(e)
        if (
            e.get("type") == "item.started"
            and e.get("item", {}).get("type") == "command_execution"
        ):
            started.set()

    job = asyncio.create_task(
        cli.run(
            agent_id="cancelcheck",
            cwd=repo,
            prompt="Cancellation acceptance check: run Start-Sleep -Seconds 30 in PowerShell, then return JSON message done. Do not read or change any files.",
            model="gpt-6-luna",
            effort="low",
            schema=obj({"message": STR}),
            output=output,
            timeout=60,
            windows_sandbox="unelevated",
            event=event,
        )
    )
    try:
        await asyncio.wait_for(started.wait(), 40)
        await asyncio.sleep(0.5)
        proc = cli.processes["cancelcheck"]
        pid = proc.pid
        descendants = [p.pid for p in psutil.Process(pid).children(recursive=True)]
        await cli.cancel("cancelcheck")
        try:
            await job
            cancelled = False
        except CodexError:
            cancelled = True
        await asyncio.sleep(0.5)
        result = {
            "cancelled_live_codex": cancelled,
            "parent_pid": pid,
            "descendant_pids": descendants,
            "surviving_pids": [p for p in [pid, *descendants] if psutil.pid_exists(p)],
        }
        output.mkdir(exist_ok=True, parents=True)
        (output / "cancellation.json").write_text(json.dumps(result, indent=2))
        print(json.dumps(result, indent=2))
        assert cancelled and not result["surviving_pids"]
    finally:
        await cli.cancel()
        if not job.done():
            job.cancel()
        await asyncio.gather(job, return_exceptions=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--run", action="store_true")
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    if not a.run:
        p.error("Explicit --run required")
    asyncio.run(main(a.repo.resolve(), a.output.resolve()))
