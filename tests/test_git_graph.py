import pytest
from codex_swarm.integrations.git_manager import (
    Workspace,
    GitError,
    clean,
    valid_scope,
)
from codex_swarm.core.task_graph import validate_graph, wave
from codex_swarm.core.model_router import ModelRouter


def worker(id="w1", deps=None, files=None):
    return {
        "id": id,
        "depends_on": deps or [],
        "files": files or ["a.py"],
        "write": True,
    }


def test_cycle():
    with pytest.raises(ValueError):
        validate_graph([worker("w1", ["w2"]), worker("w2", ["w1"])], 10, True)


def test_readonly_plan():
    with pytest.raises(ValueError):
        validate_graph([worker()], 10, False)


def test_conflict_wave():
    result = wave([worker(), worker("w2"), worker("w3", files=["b.py"])], 3)
    assert [w["id"] for w in result] == ["w1", "w3"]


@pytest.mark.parametrize(
    "scope",
    ["../a", "/etc", "C:/test", ".git/config", "a/../../b", "foo\\bar", "*.py", ""],
)
def test_bad_scope(scope):
    assert not valid_scope(scope)


def test_isolate_integrate_promote(repo, tmp_path):
    ws = Workspace(repo, tmp_path / "trees", "test1")
    assert ws.branch == "codex-swarm/test1/integration"
    base = ws.create()
    a, ab = ws.worker("w1", 1)
    b, bb = ws.worker("w2", 1)
    (a / "a.py").write_text("def add(a,b): return a+b\n")
    (b / "b.py").write_text("def mul(a,b): return a*b\n")
    _, af = ws.commit_worker(a, ["a.py"], ab)
    _, bf = ws.commit_worker(b, ["b.py"], bb)
    ws.integrate(a, ab, af)
    ws.integrate(b, bb, bf)
    assert "a - b" in (repo / "a.py").read_text()
    assert clean(repo)
    ws.promote(base)
    assert "a+b" in (repo / "a.py").read_text()
    assert "a*b" in (repo / "b.py").read_text()


def test_resume_legacy_integration_branch(repo, tmp_path):
    root = tmp_path / "legacy-trees"
    original = Workspace(repo, root, "oldrun")
    original.branch = "nexus/oldrun/integration"
    base = original.create()
    restored = Workspace(repo, root, "oldrun")
    assert restored.branch == original.branch
    restored.promote(base)


def test_dirty_repo_preserved(repo, tmp_path):
    (repo / "a.py").write_text("USER EDIT")
    with pytest.raises(GitError):
        Workspace(repo, tmp_path / "trees", "dirty").create()
    assert (repo / "a.py").read_text() == "USER EDIT"


def test_out_of_scope(repo, tmp_path):
    ws = Workspace(repo, tmp_path / "trees", "scope")
    ws.create()
    p, b = ws.worker("w1", 1)
    (p / "b.py").write_text("other")
    with pytest.raises(GitError):
        ws.commit_worker(p, ["a.py"], b)


def test_conflict_retained(repo, tmp_path):
    ws = Workspace(repo, tmp_path / "trees", "conflict")
    ws.create()
    a, ab = ws.worker("w1", 1)
    b, bb = ws.worker("w2", 1)
    (a / "a.py").write_text("first")
    (b / "a.py").write_text("second")
    _, af = ws.commit_worker(a, ["a.py"], ab)
    _, bf = ws.commit_worker(b, ["a.py"], bb)
    ws.integrate(a, ab, af)
    with pytest.raises(GitError):
        ws.integrate(b, bb, bf)
    assert clean(ws.integration)
    assert (b / "a.py").read_text() == "second"


def test_catalog_validates():
    r = ModelRouter(
        [
            {
                "model": "actual",
                "defaultReasoningEffort": "low",
                "supportedReasoningEfforts": [{"reasoningEffort": "low"}],
                "isDefault": True,
            }
        ]
    )
    assert r.select() == ("actual", "low")
    with pytest.raises(ValueError):
        r.select("invented")
    with pytest.raises(ValueError):
        r.select("actual", "high")


def test_deletion_requires_manual_review(repo, tmp_path):
    ws = Workspace(repo, tmp_path / "trees", "deletion")
    ws.create()
    p, b = ws.worker("w1", 1)
    (p / "a.py").unlink()
    with pytest.raises(GitError, match="deletion"):
        ws.commit_worker(p, ["a.py"], b)
    assert (repo / "a.py").exists()


def test_host_filter_blocked(repo):
    from codex_swarm.integrations.git_manager import project_path

    (repo / ".gitattributes").write_text("*.py filter=custom\n")
    with pytest.raises(GitError, match="filters"):
        project_path(str(repo))
