from pathlib import Path

import termlit.cli as termlit_cli


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
