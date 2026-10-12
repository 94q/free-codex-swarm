from __future__ import annotations
import argparse
import asyncio
import json
import sys
from pathlib import Path
from codex_swarm.persistence.config import Config
from codex_swarm.persistence.database import Database
from codex_swarm.persistence.lock import InstanceLock


async def doctor(config: Config) -> None:
    from codex_swarm.integrations.codex_cli import CodexCLI

    cli = CodexCLI(config.value["engine"]["codex_binary"])
    status = await cli.auth_status()
    print("Native CLI:", cli.binary)
    print("Default-home authentication:", status)
    data = await cli.metadata()
    print(data["catalog_note"])
    for m in data["models"]:
        print(
            m["model"],
            ", ".join(e["reasoningEffort"] for e in m["supportedReasoningEfforts"]),
        )


def main() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(
        description="Codex-Swarm — official Codex CLI, ChatGPT authentication, isolated workers"
    )
    parser.add_argument(
        "--home",
        type=Path,
        help="Codex-Swarm settings/history directory; not the Codex credential home",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Check CLI, authentication and model catalog; no inference",
    )
    parser.add_argument("--project", help="Headless run in a clean Git repository")
    parser.add_argument("--prompt", help="Headless task objective")
    parser.add_argument("--resume", help="Resume a saved task ID (headless)")
    parser.add_argument(
        "--reset-settings",
        action="store_true",
        help="Back up and reset all preferences; preserve task records and Codex authentication",
    )
    parser.add_argument(
        "--no-resize", action="store_true", help="Leave terminal window size unchanged"
    )
    args = parser.parse_args()
    config = Config(args.home)
    try:
        with InstanceLock(config.root):
            reset_request = config.root / "reset-settings.request"
            if args.reset_settings or reset_request.exists():
                config.reset()
                reset_request.unlink(missing_ok=True)
            if args.doctor:
                asyncio.run(doctor(config))
                return
            db = Database(config.root)
            try:
                if args.project or args.resume:
                    from codex_swarm.core.orchestrator import Orchestrator

                    if args.resume:
                        t = db.get(args.resume)
                        args.project = t["project"]
                        args.prompt = t["prompt"]
                    if not args.prompt:
                        parser.error("--project requires --prompt")
                    db.recover()
                    engine = Orchestrator(
                        config,
                        db,
                        listener=lambda a, e: print(
                            json.dumps({"agent": a, **e}, ensure_ascii=False),
                            flush=True,
                        ),
                    )
                    result = asyncio.run(
                        engine.run(args.project, args.prompt, resume=args.resume or "")
                    )
                    print(
                        json.dumps(
                            {
                                "task": result["id"],
                                "status": result["status"],
                                "report": result.get("report"),
                                "error": result.get("error"),
                            },
                            indent=2,
                        )
                    )
                    if result["status"] not in {"ready", "promoted"}:
                        sys.exit(1)
                else:
                    from codex_swarm.tui.app import SwarmApp
                    from codex_swarm.tui.banner import recommended_size
                    from codex_swarm.tui.terminal import fit_terminal

                    app = SwarmApp(config, db)
                    if not args.no_resize:
                        app.startup_notice = fit_terminal(
                            recommended_size(config.value["appearance"])
                        ).notice
                    app.run()
            finally:
                db.close()
    except KeyboardInterrupt:
        print("Interrupted; preserved task checkpoints.")
    except (RuntimeError, ValueError, OSError) as exc:
        print(f"Codex-Swarm: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
