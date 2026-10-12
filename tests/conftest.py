import pytest
from codex_swarm.integrations.git_manager import git


@pytest.fixture
def repo(tmp_path):
    p = tmp_path / "repo"
    p.mkdir()
    git(p, "init")
    (p / "a.py").write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")
    (p / "b.py").write_text("def mul(a, b):\n    return a + b\n", encoding="utf-8")
    (p / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    git(p, "add", ".")
    git(
        p,
        "-c",
        "user.name=Swarm Test",
        "-c",
        "user.email=test@localhost",
        "commit",
        "-m",
        "fixture",
    )
    return p
