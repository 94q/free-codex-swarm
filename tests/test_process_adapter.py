import asyncio
import os
from pathlib import Path
import sys
import pytest
import psutil
from codex_swarm.integrations.codex_cli import CodexCLI, CodexError, spawn_options
from codex_swarm.integrations.process_guard import ProcessGuard
from codex_swarm.core.coordinator import obj, STR


@pytest.fixture
def adapter(tmp_path, monkeypatch):
    script = tmp_path / "child.py"
    script.write_text("""import json,sys,time
mode=sys.argv[1]
sys.stdin.read()
print(json.dumps({"type":"thread.started","thread_id":"test-thread"}),flush=True)
if mode=="timeout": time.sleep(20)
if mode=="bad":
 print("not json",flush=True)
 sys.exit(2)
print(json.dumps({"type":"item.completed","item":{"type":"agent_message","text":'{"message":"okay"}'}}),flush=True)
print(json.dumps({"type":"turn.completed","usage":{"input_tokens":3,"output_tokens":2}}),flush=True)
""")
    original = asyncio.create_subprocess_exec
    captured = []

    async def spawn(*args, **kwargs):
        captured.append(args)
        if Path(args[0]).resolve() == Path(sys.executable).resolve():
            agent = Path(args[args.index("--output-schema") + 1]).stem.split(".")[0]
            return await original(sys.executable, str(script), agent, **kwargs)
        return await original(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", spawn)
    cli = CodexCLI(sys.executable)
    cli.test_captured_args = captured

    async def auth(home=""):
        return "ChatGPT"

    monkeypatch.setattr(cli, "auth_status", auth)
    return cli


async def test_real_child_json_stream(adapter, tmp_path):
    events = []
    r = await adapter.run(
        agent_id="okay",
        cwd=tmp_path,
        prompt="hello",
        model="test",
        effort="low",
        schema=obj({"message": STR}),
        output=tmp_path / "protocol",
        event=events.append,
    )
    assert r.usage["input_tokens"] == 3
    assert r.thread_id == "test-thread"
    assert [e["type"] for e in events][-1] == "process.exited"
    assert not adapter.processes
    command = adapter.test_captured_args[0]
    assert any('windows.sandbox=' in str(arg) for arg in command) == (os.name == "nt")


async def test_timeout_reaps_process(adapter, tmp_path):
    events = []
    with pytest.raises(TimeoutError):
        await adapter.run(
            agent_id="timeout",
            cwd=tmp_path,
            prompt="hello",
            model="test",
            effort="low",
            schema=obj({"message": STR}),
            output=tmp_path / "protocol",
            event=events.append,
            timeout=0.3,
        )
    pid = events[0]["pid"]
    assert not psutil.pid_exists(pid)
    assert not adapter.processes


async def test_cancel_reaps_process(adapter, tmp_path):
    events = []
    job = asyncio.create_task(
        adapter.run(
            agent_id="timeout",
            cwd=tmp_path,
            prompt="hello",
            model="test",
            effort="low",
            schema=obj({"message": STR}),
            output=tmp_path / "protocol",
            event=events.append,
            timeout=20,
        )
    )
    while not adapter.processes:
        await asyncio.sleep(0.01)
    await adapter.cancel("timeout")
    with pytest.raises(CodexError):
        await job
    assert not psutil.pid_exists(events[0]["pid"])


async def test_protocol_error(adapter, tmp_path):
    with pytest.raises(CodexError):
        await adapter.run(
            agent_id="bad",
            cwd=tmp_path,
            prompt="hello",
            model="test",
            effort="low",
            schema=obj({"message": STR}),
            output=tmp_path / "protocol",
        )


async def test_cancel_during_auth_never_spawns(adapter, tmp_path, monkeypatch):
    begun = asyncio.Event()
    release = asyncio.Event()

    async def delayed_auth(home=""):
        begun.set()
        await release.wait()
        return "ChatGPT"

    monkeypatch.setattr(adapter, "auth_status", delayed_auth)
    events = []
    job = asyncio.create_task(
        adapter.run(
            agent_id="okay",
            cwd=tmp_path,
            prompt="hello",
            model="test",
            effort="low",
            schema=obj({"message": STR}),
            output=tmp_path / "protocol",
            event=events.append,
        )
    )
    await begun.wait()
    await adapter.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await job
    assert not events and not adapter.processes


@pytest.mark.skipif(os.name != "nt", reason="Windows Job Object integration")
async def test_job_closure_kills_descendants(tmp_path):
    script = tmp_path / "tree.py"
    script.write_text("""import subprocess,sys,time
p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
print(p.pid,flush=True)
time.sleep(30)
""")
    p = await asyncio.create_subprocess_exec(
        sys.executable, str(script), stdout=asyncio.subprocess.PIPE, **spawn_options()
    )
    guard = ProcessGuard(p.pid)
    child = int(await asyncio.wait_for(p.stdout.readline(), 5))
    guard.close()
    await asyncio.wait_for(p.wait(), 5)
    for _ in range(20):
        if not psutil.pid_exists(child):
            break
        await asyncio.sleep(0.05)
    assert not psutil.pid_exists(child)
