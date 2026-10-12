import subprocess
import sys
from codex_swarm.persistence.lock import InstanceLock


def test_os_lock_excludes_second_process(tmp_path):
    script = "from pathlib import Path; from codex_swarm.persistence.lock import InstanceLock; import sys;\nwith InstanceLock(Path(sys.argv[1])): print('owned')"
    with InstanceLock(tmp_path):
        p = subprocess.run(
            [sys.executable, "-c", script, str(tmp_path)],
            capture_output=True,
            text=True,
        )
        assert p.returncode != 0
        assert "Another Codex-Swarm" in p.stderr
    p = subprocess.run(
        [sys.executable, "-c", script, str(tmp_path)], capture_output=True, text=True
    )
    assert p.returncode == 0


def test_stale_metadata_is_not_lock_authority(tmp_path):
    (tmp_path / "instance.lock").write_text("invalid stale metadata")
    with InstanceLock(tmp_path):
        pass
