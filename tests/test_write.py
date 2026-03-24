import pytest

from termlit import session as sess


class FakeChannel:
    def __init__(self):
        self.sent = []
        self.closed = False

    def send(self, data):
        # paramiko.Channel.send returns number of bytes written; capture payload
        self.sent.append(data)
        return len(data)


def _decoded_sent(channel: FakeChannel):
    return [b.decode("utf-8", errors="ignore") for b in channel.sent]


def test_write_non_stream_with_newlines():
    ch = FakeChannel()
    s = sess.TermlitSession(channel=ch, username="tester")
    sess.bind_session(s)
    try:
        sess.write("Hello\nWorld\n")
        sent = _decoded_sent(ch)
        assert len(sent) == 1
        assert sent[0] == "Hello\r\nWorld\r\n"
        print('test: ' + sent[0])
        print('exected: ' + "Hello\r\nWorld\r\n")
    finally:
        sess.unbind_session()


def test_write_non_stream_no_newline():
    ch = FakeChannel()
    s = sess.TermlitSession(channel=ch, username="tester")
    sess.bind_session(s)
    try:
        sess.write("Hello World")
        sent = _decoded_sent(ch)
        assert len(sent) == 1
        # send() will append a newline when missing and then convert to CRLF
        assert sent[0] == "Hello World\r\n"
        print('test: ' + sent[0])
        print('exected: ' + "Hello World\r\n")
    finally:
        sess.unbind_session()


def test_write_stream_chunks_with_trailing_newlines():
    ch = FakeChannel()
    s = sess.TermlitSession(channel=ch, username="tester")
    sess.bind_session(s)
    try:
        sess.write(["line1\n", "line2\n"], stream=True)
        sent = _decoded_sent(ch)
        # two chunks should be sent, each with CRLF translation
        assert len(sent) == 2
        assert sent[0] == "line1\r\n"
        assert sent[1] == "line2\r\n"
    finally:
        sess.unbind_session()


def test_write_stream_chunks_missing_final_newline_adds_one():
    ch = FakeChannel()
    s = sess.TermlitSession(channel=ch, username="tester")
    sess.bind_session(s)
    try:
        # final chunk does not end with newline -> write will emit an extra empty send()
        sess.write(["a\n", "b"], stream=True)
        sent = _decoded_sent(ch)
        # first: "a\r\n", second: "b" (no newline added by session.send), third: final empty send -> CRLF
        assert len(sent) == 3
        assert sent[0] == "a\r\n"
        assert sent[1] == "b"
        assert sent[2] == "\r\n"
    finally:
        sess.unbind_session()


def test_welcome_renders_banner_tips_and_info_panel():
    ch = FakeChannel()
    s = sess.TermlitSession(channel=ch, username="tester")
    sess.bind_session(s)
    try:
        sess.welcome(
            title="Welcome",
            panel_title="Termlit",
            subtitle="version 1.0.0",
            description="This is a note",
        )
        output = "".join(_decoded_sent(ch))
        assert "Tips for getting started:" in output
        assert "Ask questions, edit files, or run commands." in output
        assert "/help for more information." in output
        assert "You are running " in output
        assert "Termlit" in output
        assert "This is a note" in output
    finally:
        sess.unbind_session()


def test_spinner_is_disabled_when_debugger_is_attached(monkeypatch):
    ch = FakeChannel()
    s = sess.TermlitSession(channel=ch, username="tester")
    sess.bind_session(s)
    monkeypatch.setattr(sess.sys, "gettrace", lambda: object())
    try:
        with sess.spinner("dots", "Processing your request..."):
            sess.write("inside spinner")
        output = "".join(_decoded_sent(ch))
        assert "inside spinner" in output
        assert "Processing your request..." not in output
    finally:
        sess.unbind_session()


def test_spinner_uses_stdio_for_local_session(monkeypatch):
    s = sess.LocalSession(username="tester")
    sess.bind_session(s)
    monkeypatch.setattr(sess.os, "name", "nt")
    monkeypatch.setattr(sess.sys, "gettrace", lambda: None)
    try:
        ctx = sess.spinner("dots", "Processing your request...")
        assert ctx.enabled is True
        assert ctx.local_stdio is True
    finally:
        sess.unbind_session()
