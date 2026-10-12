"""Official CLI adapter: JSONL execution and short-lived metadata-only RPC."""

from __future__ import annotations
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import re
from dataclasses import dataclass, field
from typing import Callable, Any
from codex_swarm.core.security import child_env, redact
from codex_swarm.integrations.process_guard import ProcessGuard


class CodexError(RuntimeError):
    pass


def executable(override: str = "") -> str:
    if override:
        p = Path(override).expanduser().resolve()
        if not p.is_file() or (os.name == "nt" and p.suffix.lower() != ".exe"):
            raise CodexError("Select the native codex.exe, not a shell script.")
        return str(p)
    found = shutil.which("codex.exe" if os.name == "nt" else "codex")
    candidates = [Path(found)] if found else []
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA", "")) / "npm/node_modules/@openai/codex"
        candidates.extend(root.glob("**/bin/codex.exe"))
        app_root = Path(os.environ.get("LOCALAPPDATA", "")) / "OpenAI/Codex/bin"
        candidates.extend(app_root.glob("*/codex.exe"))
        standalone = (
            Path(os.environ.get("LOCALAPPDATA", ""))
            / "Programs/OpenAI/Codex/bin/codex.exe"
        )
        if standalone.is_file():
            candidates.append(standalone)

    def version(p: Path):
        try:
            result = subprocess.run(
                [str(p), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            match = re.search(r"(\d+)\.(\d+)\.(\d+)", result.stdout)
            return tuple(map(int, match.groups())) if match else (0, 0, 0)
        except (OSError, subprocess.TimeoutExpired):
            return (0, 0, 0)

    if candidates:
        return str(max(dict.fromkeys(candidates), key=version))
    raise CodexError(
        "Codex CLI not found. Install official @openai/codex, then run codex login."
    )


async def kill_tree(process: asyncio.subprocess.Process) -> None:
    if process.returncode is not None:
        return
    if os.name == "nt":
        killer = await asyncio.create_subprocess_exec(
            "taskkill",
            "/PID",
            str(process.pid),
            "/T",
            "/F",
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        await killer.wait()
    else:
        import signal

        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    await process.wait()


def spawn_options() -> dict:
    return (
        {"creationflags": subprocess.CREATE_NO_WINDOW}
        if os.name == "nt"
        else {"start_new_session": True}
    )


@dataclass
class Result:
    text: str
    usage: dict = field(default_factory=dict)
    thread_id: str = ""
    elapsed: float = 0


class CodexCLI:
    def __init__(self, binary: str = ""):
        self.binary = executable(binary)
        self.processes: dict[str, asyncio.subprocess.Process] = {}
        self.cancel_epoch = 0
        self.agent_cancel_epochs: dict[str, int] = {}

    async def auth_status(self, home: str = "") -> str:
        p = await asyncio.create_subprocess_exec(
            self.binary,
            "login",
            "status",
            env=child_env(home),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            **spawn_options(),
        )
        try:
            out, err = await asyncio.wait_for(p.communicate(), 20)
        except BaseException:
            await kill_tree(p)
            raise
        msg = (out + err).decode("utf-8", "replace")
        if p.returncode == 0 and "ChatGPT" in msg:
            return "ChatGPT"
        if "API key" in msg or "api key" in msg:
            return "API key (blocked by Codex-Swarm)"
        return "Not authenticated"

    async def metadata(self, home: str = "") -> dict:
        # No inference here; stdout/stderr is not persisted. Never inspect auth.json.
        p = await asyncio.create_subprocess_exec(
            self.binary,
            "app-server",
            "--listen",
            "stdio://",
            "-c",
            'model_provider="openai"',
            env=child_env(home),
            stdout=subprocess.PIPE,
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            limit=4 * 1024 * 1024,
            **spawn_options(),
        )

        async def rpc(i: int, method: str, params: dict) -> Any:
            p.stdin.write(
                (
                    json.dumps({"id": i, "method": method, "params": params}) + "\n"
                ).encode()
            )
            await p.stdin.drain()
            while True:
                raw = await asyncio.wait_for(p.stdout.readline(), 40)
                if not raw:
                    raise CodexError("App-server closed before responding to " + method)
                msg = json.loads(raw)
                if msg.get("id") == i:
                    if "error" in msg:
                        raise CodexError(redact(str(msg["error"])))
                    return msg.get("result")
                if "id" in msg and "method" in msg:
                    p.stdin.write(
                        (
                            json.dumps(
                                {
                                    "id": msg["id"],
                                    "error": {
                                        "code": -32601,
                                        "message": "Metadata client cannot approve actions",
                                    },
                                }
                            )
                            + "\n"
                        ).encode()
                    )

        try:
            await rpc(
                1,
                "initialize",
                {
                    "clientInfo": {
                        "name": "codex_swarm",
                        "title": "Codex-Swarm",
                        "version": "0.1.0",
                    }
                },
            )
            p.stdin.write(b'{"method":"initialized","params":{}}\n')
            await p.stdin.drain()
            models, cursor, i = [], None, 2
            while True:
                page = await rpc(
                    i,
                    "model/list",
                    {"limit": 100, "includeHidden": False, "cursor": cursor},
                )
                models.extend(page["data"])
                cursor = page.get("nextCursor")
                i += 1
                if not cursor:
                    break
            try:
                limits = await rpc(i, "account/rateLimits/read", {})
            except CodexError as exc:
                limits = {"unavailable": str(exc)}
            return {
                "models": models,
                "limits": limits,
                "catalog_note": "Catalog is not an entitlement guarantee; successful inference verifies access.",
            }
        finally:
            await kill_tree(p)

    async def cancel(self, agent_id: str | None = None) -> None:
        if agent_id is None:
            self.cancel_epoch += 1
        else:
            self.agent_cancel_epochs[agent_id] = (
                self.agent_cancel_epochs.get(agent_id, 0) + 1
            )
        processes = (
            [self.processes[agent_id]]
            if agent_id in self.processes
            else ([] if agent_id else list(self.processes.values()))
        )
        await asyncio.gather(*(kill_tree(p) for p in processes))

    async def run(
        self,
        *,
        agent_id: str,
        cwd: Path,
        prompt: str,
        model: str,
        effort: str,
        schema: dict,
        output: Path,
        home: str = "",
        writable: bool = False,
        timeout: int = 900,
        windows_sandbox: str = "elevated",
        event: Callable[[dict], None] = lambda e: None,
    ) -> Result:
        epoch = self.cancel_epoch
        agent_epoch = self.agent_cancel_epochs.get(agent_id, 0)

        def cancelled() -> bool:
            return (
                epoch != self.cancel_epoch
                or agent_epoch != self.agent_cancel_epochs.get(agent_id, 0)
            )

        if windows_sandbox not in {"elevated", "unelevated"}:
            raise CodexError("Unsupported Windows sandbox implementation")
        if await self.auth_status(home) != "ChatGPT":
            raise CodexError(
                "ChatGPT authentication required. API-key sessions are not used."
            )
        if cancelled():
            raise asyncio.CancelledError()
        output.mkdir(parents=True, exist_ok=True)
        schema_file = output / f"{agent_id}.schema.json"
        schema_file.write_text(json.dumps(schema), encoding="utf-8")
        args = [
            self.binary,
            "-a",
            "never",
            "exec",
            "--ignore-user-config",
            "--ignore-rules",
            "--json",
            "--color",
            "never",
            "--sandbox",
            "workspace-write" if writable else "read-only",
            "--model",
            model,
            "-c",
            'model_provider="openai"',
            "-c",
            'forced_login_method="chatgpt"',
            "-c",
            f'model_reasoning_effort="{effort}"',
            "-c",
            "features.multi_agent=false",
            "-c",
            f'windows.sandbox="{windows_sandbox}"',
            "-c",
            'web_search="disabled"',
            "-c",
            "sandbox_workspace_write.network_access=false",
            "--cd",
            str(cwd),
            "--output-schema",
            str(schema_file),
            "-",
        ]
        from codex_swarm.core.coordinator import POLICY

        args[1:1] = ["-c", "developer_instructions=" + json.dumps(POLICY)]
        started = time.monotonic()
        p = await asyncio.create_subprocess_exec(
            *args,
            env=child_env(home),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            limit=4 * 1024 * 1024,
            **spawn_options(),
        )
        if cancelled():
            await kill_tree(p)
            raise asyncio.CancelledError()
        try:
            guard = ProcessGuard(p.pid)
        except Exception:
            await kill_tree(p)
            raise
        self.processes[agent_id] = p
        event(
            {"type": "process.started", "pid": p.pid, "model": model, "effort": effort}
        )
        result = Result("")
        completed = False
        errors: list[str] = []

        async def read_stdout() -> None:
            nonlocal completed
            async for raw in p.stdout:
                try:
                    msg = json.loads(raw)
                except (ValueError, UnicodeError):
                    event(
                        {
                            "type": "protocol.warning",
                            "message": redact(raw.decode("utf-8", "replace"))[:2000],
                        }
                    )
                    continue
                # Scrub both persisted and UI events, while preserving JSON structure.
                msg = json.loads(json.dumps(msg, ensure_ascii=False))

                def clean(v):
                    if isinstance(v, str):
                        return redact(v)
                    if isinstance(v, dict):
                        return {
                            k: (
                                "[REDACTED]"
                                if any(
                                    s in k.lower()
                                    for s in (
                                        "token_value",
                                        "access_token",
                                        "refresh_token",
                                        "id_token",
                                        "api_key",
                                    )
                                )
                                else clean(x)
                            )
                            for k, x in v.items()
                        }
                    if isinstance(v, list):
                        return [clean(x) for x in v]
                    return v

                msg = clean(msg)
                event(msg)
                if msg.get("type") == "thread.started":
                    result.thread_id = msg.get("thread_id", "")
                if msg.get("type") == "turn.completed":
                    completed = True
                    result.usage = msg.get("usage", {})
                if msg.get("type") in {"turn.failed", "error"}:
                    errors.append(str(msg))
                item = msg.get("item", {})
                if (
                    msg.get("type") == "item.completed"
                    and item.get("type") == "agent_message"
                ):
                    result.text = item.get("text", "")

        async def read_stderr() -> None:
            async for raw in p.stderr:
                msg = redact(raw.decode("utf-8", "replace"))[:4000]
                event({"type": "stderr", "message": msg})
                errors.append(msg)
                del errors[:-20]

        readers = [
            asyncio.create_task(read_stdout()),
            asyncio.create_task(read_stderr()),
        ]
        try:
            p.stdin.write(prompt.encode("utf-8"))
            await p.stdin.drain()
            p.stdin.close()
            await asyncio.wait_for(asyncio.gather(p.wait(), *readers), timeout)
            if p.returncode != 0 or not completed or not result.text:
                raise CodexError(
                    redact(f"Codex failed (exit {p.returncode}); " + "\n".join(errors))[
                        -6000:
                    ]
                )
            result.elapsed = time.monotonic() - started
            return result
        except BaseException:
            await kill_tree(p)
            for reader in readers:
                reader.cancel()
            await asyncio.gather(*readers, return_exceptions=True)
            raise
        finally:
            guard.close()
            self.processes.pop(agent_id, None)
            event(
                {
                    "type": "process.exited",
                    "exit_code": p.returncode,
                    "elapsed": round(time.monotonic() - started, 2),
                }
            )
