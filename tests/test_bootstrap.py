from pathlib import Path
import subprocess
import sys
import pytest
from scripts import bootstrap


@pytest.mark.parametrize("existing", [False, True])
def test_installer_uses_local_venv_and_project_requirements(
    tmp_path, monkeypatch, existing
):
    python = bootstrap.venv_python(tmp_path)
    if existing:
        python.parent.mkdir(parents=True)
        python.touch()
    calls = []
    monkeypatch.setattr(
        subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs))
    )
    bootstrap.install(tmp_path)
    if not existing:
        assert calls[0][0] == [sys.executable, "-m", "venv", str(tmp_path / ".venv")]
    else:
        assert len(calls) == 3
    assert calls[-2][0] == [
        str(python),
        "-m",
        "pip",
        "install",
        "-r",
        "requirements.txt",
    ]
    assert calls[-2][1]["cwd"] == tmp_path
    assert calls[-1][0][-2:] == ["pip", "check"]
    assert all(kwargs["check"] for _, kwargs in calls)


def test_installer_rejects_old_python(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "version_info", (3, 10))
    with pytest.raises(RuntimeError, match="3.11"):
        bootstrap.install(tmp_path)


def test_installer_reports_errors(monkeypatch, capsys):
    def fail(root):
        raise OSError("fixture failure")

    monkeypatch.setattr(bootstrap, "install", fail)
    assert bootstrap.main() == 1
    assert "Installation failed" in capsys.readouterr().err


def test_batch_files_and_requirements_present():
    root = Path(__file__).resolve().parents[1]
    assert (root / "requirements.txt").read_text().splitlines()[-1] == "."
    for name in ("run.bat", "install_requirements.bat"):
        text = (root / name).read_text()
        assert 'pushd "%~dp0"' in text
        assert "ExecutionPolicy" not in text
