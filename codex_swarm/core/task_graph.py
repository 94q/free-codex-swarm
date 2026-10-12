from __future__ import annotations
import re
from codex_swarm.integrations.git_manager import valid_scope


def validate_graph(workers: list[dict], budget: int, writable: bool) -> None:
    if len(workers) > budget - 2:
        raise ValueError("Plan exceeds invocation budget (reserve planning + review)")
    ids = [w["id"] for w in workers]
    if len(ids) != len(set(ids)) or any(
        not re.fullmatch(r"w[0-9]{1,3}", x) for x in ids
    ):
        raise ValueError("Worker IDs must be unique w1, w2, ...")
    for w in workers:
        if w["id"] in w["depends_on"] or not set(w["depends_on"]) <= set(ids):
            raise ValueError("Invalid dependency")
        if w["write"] and not writable:
            raise ValueError("Planner requested writes under read-only permissions")
        if w["write"] and not w["files"]:
            raise ValueError("Writing tasks need explicit file or directory scope")
        if any(not valid_scope(f) for f in w["files"]):
            raise ValueError("Unsafe scope; use relative paths or directory/ prefixes")
    remaining, done = list(workers), set()
    while remaining:
        ready = [w for w in remaining if set(w["depends_on"]) <= done]
        if not ready:
            raise ValueError("Dependency cycle in plan")
        done.update(w["id"] for w in ready)
        remaining = [w for w in remaining if w not in ready]


def ready_workers(workers: list[dict], agents: dict) -> list[dict]:
    return [
        w
        for w in workers
        if agents.get(w["id"], {}).get("status") != "completed"
        and all(agents.get(d, {}).get("status") == "completed" for d in w["depends_on"])
    ]


def conflict(a: dict, b: dict) -> bool:
    if not (a["write"] and b["write"]):
        return False
    return any(
        x == y
        or (x.endswith("/") and y.startswith(x))
        or (y.endswith("/") and x.startswith(y))
        for x in a["files"]
        for y in b["files"]
    )


def wave(ready: list[dict], limit: int) -> list[dict]:
    result = []
    for w in ready:
        if len(result) < limit and not any(conflict(w, x) for x in result):
            result.append(w)
    return result
