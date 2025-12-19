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
