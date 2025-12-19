import tempfile
import unittest
from pathlib import Path

import pytest

from termlit import session as session_mod


class DummySession:
    def __init__(self):
        self.messages: list[str] = []
        self.username = "tester"

    def send(self, message: str = "", newline: bool = True) -> None:
        self.messages.append(message)


class UploadFileReplaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.session = DummySession()
        session_mod.bind_session(self.session)

    def tearDown(self) -> None:
        session_mod.unbind_session()
        self._tmp.cleanup()

    def test_replace_same_path_skips_copy(self) -> None:
        source = self.base / "report.txt"
        source.write_text("payload")

        result = session_mod.upload_file(
            source,
            destination_dir=self.base,
            replace=True,
            show_progress=True,
        )

        self.assertEqual(result, source)
        self.assertEqual(source.read_text(), "payload")
        self.assertTrue(
            any("skipped self-copy" in msg for msg in self.session.messages),
            msg=self.session.messages,
        )


class FakeChannel:
    def __init__(self):
        self.sent: list[bytes] = []
        self.closed = False

    def send(self, data):
        self.sent.append(data)
        return len(data)


def _decoded_sent(channel: FakeChannel):
    return [b.decode("utf-8", errors="ignore") for b in channel.sent]


def test_upload_file_ssh_session_logs_message(tmp_path: Path) -> None:
    source = tmp_path / "report.txt"
    source.write_text("payload")
    dest_dir = tmp_path / "uploads"

    channel = FakeChannel()
    session = session_mod.TermlitSession(channel=channel, username="tester")
    session_mod.bind_session(session)
    try:
        result = session_mod.upload_file(
            source,
            destination_dir=dest_dir,
            replace=True,
            show_progress=False,
        )
    finally:
        session_mod.unbind_session()

    assert isinstance(result, Path)
    assert result.exists()
    assert result.read_text() == "payload"
    sent = "".join(_decoded_sent(channel))
    assert "[UPLOAD]" in sent
    assert "report.txt" in sent


def test_upload_file_local_session_logs_message(tmp_path: Path, capsys) -> None:
    source = tmp_path / "notes.txt"
    source.write_text("payload")
    dest_dir = tmp_path / "uploads"

    session = session_mod.LocalSession(username="local")
    session_mod.bind_session(session)
    try:
        result = session_mod.upload_file(
            source,
            destination_dir=dest_dir,
            replace=True,
            show_progress=False,
        )
    finally:
        session_mod.unbind_session()

    assert isinstance(result, Path)
    assert result.exists()
    assert result.read_text() == "payload"
    captured = capsys.readouterr()
    assert "[UPLOAD]" in captured.out
    assert "notes.txt" in captured.out


def test_upload_files_multiple_local_session(tmp_path: Path, capsys) -> None:
    source_a = tmp_path / "a.txt"
    source_b = tmp_path / "b.txt"
    source_a.write_text("alpha")
    source_b.write_text("beta")
    dest_dir = tmp_path / "uploads"

    session = session_mod.LocalSession(username="local")
    session_mod.bind_session(session)
    try:
        result = session_mod.upload_files(
            [source_a, source_b],
            destination_dir=dest_dir,
            replace=True,
            show_progress=False,
        )
    finally:
        session_mod.unbind_session()

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(path.exists() for path in result)
    captured = capsys.readouterr()
    assert "a.txt" in captured.out
    assert "b.txt" in captured.out


def test_upload_file_show_progress_local_session(tmp_path: Path, capsys) -> None:
    source = tmp_path / "progress.txt"
    source.write_text("payload")
    dest_dir = tmp_path / "uploads"

    session = session_mod.LocalSession(username="local")
    session_mod.bind_session(session)
    try:
        result = session_mod.upload_file(
            source,
            destination_dir=dest_dir,
            replace=True,
            show_progress=True,
        )
    finally:
        session_mod.unbind_session()

    assert isinstance(result, Path)
    assert result.exists()
    captured = capsys.readouterr()
    assert "[UPLOAD]" in captured.out
    assert "100%" in captured.out


def test_upload_file_show_progress_ssh_session(tmp_path: Path) -> None:
    source = tmp_path / "progress_ssh.txt"
    source.write_text("payload")
    dest_dir = tmp_path / "uploads"

    channel = FakeChannel()
    session = session_mod.TermlitSession(channel=channel, username="tester")
    session_mod.bind_session(session)
    try:
        result = session_mod.upload_file(
            source,
            destination_dir=dest_dir,
            replace=True,
            show_progress=True,
        )
    finally:
        session_mod.unbind_session()

    assert isinstance(result, Path)
    assert result.exists()
    sent = "".join(_decoded_sent(channel))
    assert "[UPLOAD]" in sent
    assert "100%" in sent
