from __future__ import annotations
import json
from pathlib import Path
import sqlite3
from datetime import datetime, timezone
from codex_swarm.core.security import redact


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Database:
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(root / "history.sqlite3")
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, updated TEXT NOT NULL, data TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (seq INTEGER PRIMARY KEY, task_id TEXT, agent_id TEXT, timestamp TEXT, data TEXT);
            CREATE INDEX IF NOT EXISTS events_task ON events(task_id, seq);
            CREATE TABLE IF NOT EXISTS knowledge (project TEXT PRIMARY KEY, baseline TEXT, summary TEXT);
        """)
        self.connection.commit()

    def save(self, task: dict) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO tasks VALUES (?,?,?)",
            (task["id"], now(), json.dumps(task, ensure_ascii=False)),
        )
        self.connection.commit()

    def get(self, task_id: str) -> dict:
        row = self.connection.execute(
            "SELECT data FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        if not row:
            raise ValueError("Unknown task: " + task_id)
        return json.loads(row[0])

    def history(self) -> list[dict]:
        return [
            json.loads(r[0])
            for r in self.connection.execute(
                "SELECT data FROM tasks ORDER BY updated DESC LIMIT 200"
            )
        ]

    def event(self, task_id: str, agent_id: str, event: dict) -> None:
        # Adapter already redacts. Preserve JSON after redaction of string values.
        self.connection.execute(
            "INSERT INTO events(task_id,agent_id,timestamp,data) VALUES (?,?,?,?)",
            (task_id, agent_id, now(), json.dumps(event, ensure_ascii=False)),
        )
        self.connection.commit()

    def events(self, task_id: str, agent_id: str = "", limit: int = 500) -> list[dict]:
        rows = self.connection.execute(
            "SELECT timestamp,agent_id,data FROM events WHERE task_id=? AND (?='' OR agent_id=?) ORDER BY seq DESC LIMIT ?",
            (task_id, agent_id, agent_id, limit),
        ).fetchall()
        return [
            {"time": r[0], "agent": r[1], "event": json.loads(r[2])}
            for r in reversed(rows)
        ]

    def memory(self, project: str) -> dict:
        row = self.connection.execute(
            "SELECT baseline,summary FROM knowledge WHERE project=?", (project,)
        ).fetchone()
        return {"baseline": row[0], "summary": row[1]} if row else {}

    def remember(self, project: str, baseline: str, summary: str) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO knowledge VALUES (?,?,?)",
            (project, baseline, redact(summary)[:12000]),
        )
        self.connection.commit()

    def recover(self) -> int:
        count = 0
        for task in self.history():
            if task["status"] in {"planning", "running", "verifying", "initializing"}:
                task["status"] = "interrupted"
                for agent in task.get("agents", {}).values():
                    if agent["status"] == "running":
                        agent["status"] = "interrupted"
                self.save(task)
                count += 1
        return count

    def close(self) -> None:
        self.connection.close()
