"""OS-held, crash-released single-instance ownership of a Codex-Swarm state directory."""

from __future__ import annotations
import json
import os
from pathlib import Path
from typing import BinaryIO


class InstanceLock:
    def __init__(self, root: Path):
        self.path = root / "instance.lock"
        self.file: BinaryIO | None = None

    def __enter__(self):
        # Retain the file on exit. Deleting a lock file races with callers that
        # already opened it. The OS lock, not PID text, is authoritative.
        f = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            f.write(b"1")
            f.flush()
        f.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            f.close()
            raise RuntimeError(
                "Another Codex-Swarm instance owns this data directory"
            ) from exc
        self.file = f
        f.seek(1)
        f.truncate()
        f.write(json.dumps({"pid": os.getpid()}).encode("utf-8"))
        f.flush()
        return self

    def __exit__(self, *args):
        if self.file is not None:
            self.file.close()
            self.file = None
