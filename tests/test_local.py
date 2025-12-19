import builtins
from pathlib import Path

import termlit.cli as termlit_cli
import termlit.session as termlit_session


def _local_script_path() -> Path:
    return Path(__file__).with_name("termlit_app_for_tests_local.py")


def test_run_local_outputs_to_stdout(capsys) -> None:
    termlit_cli.main(["run", str(_local_script_path()), "--local"])
    captured = capsys.readouterr()
    assert "LOCAL_OK\n" in captured.out
    assert "LOCAL_DONE\n" in captured.out


def test_run_local_ignores_auth_flags(capsys) -> None:
    termlit_cli.main(
        [
            "run",
            str(_local_script_path()),
            "--local",
            "--auth",
            "none",
            "--user",
            "admin=password123",
            "--allow-anonymous",
        ]
    )
    captured = capsys.readouterr()
    assert "LOCAL_OK\n" in captured.out


def test_local_session_receive_line_uses_builtins_input(monkeypatch) -> None:
    def _raise_if_called(*args, **kwargs):
        raise AssertionError("termlit.session.input should not be called here")

    monkeypatch.setattr(termlit_session, "input", _raise_if_called)
    monkeypatch.setattr(builtins, "input", lambda prompt="": "hello")

    session = termlit_session.LocalSession()
    assert session.receive_line("Prompt: ") == "hello"


def test_build_app_creates_template(tmp_path, monkeypatch) -> None:
    workdir = tmp_path / "sandbox"
    workdir.mkdir()
    monkeypatch.chdir(workdir)

    termlit_cli.main(["build", "app"])

    app_path = workdir / "app.py"
    assert app_path.exists()
    contents = app_path.read_text(encoding="utf-8")
    assert "while True" in contents
