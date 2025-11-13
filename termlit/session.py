"""
Session level helpers that are exposed as the public API.

Each incoming SSH client receives its own session instance that tracks the
underlying Paramiko channel plus some metadata. The public helper functions in
this module proxy to the session stored in thread-local storage so the user
code can simply import `termlit` and call `welcome`, `input`, etc.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO, TextIOBase
import threading
import time
from typing import Dict, Optional, TYPE_CHECKING

import requests
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

if TYPE_CHECKING:  # pragma: no cover - only used for typing
    import paramiko


class SessionNotReady(RuntimeError):
    """Raised when a public helper is called outside of an active session."""


_session_local: threading.local = threading.local()


def _current_session() -> "TermlitSession":
    session: Optional["TermlitSession"] = getattr(_session_local, "session", None)
    if session is None:
        raise SessionNotReady(
            "No active Termlit session. The helper functions can only be used "
            "when a session is running inside `termlit run <script.py>`."
        )
    return session


def bind_session(session: "TermlitSession") -> None:
    """Attach a session to the current thread."""
    _session_local.session = session


def unbind_session() -> None:
    """Remove the session from the current thread."""
    if hasattr(_session_local, "session"):
        delattr(_session_local, "session")


@dataclass
class TermlitSession:
    """Wraps a Paramiko channel and exposes simple IO primitives."""

    channel: "paramiko.Channel"
    username: str

    def send(self, message: str = "", newline: bool = True) -> None:
        """Send raw text to the terminal, normalising new lines."""
        if getattr(self.channel, "closed", False):
            return
        if newline and not message.endswith("\n"):
            message += "\n"
        payload = message.replace("\n", "\r\n")
        try:
            self.channel.send(payload.encode("utf-8", errors="ignore"))
        except Exception:  # pragma: no cover - network issues
            pass

    def receive_line(
        self,
        prompt: str = "",
        *,
        allow_empty: bool = True,
        hidden: bool = False,
    ) -> str:
        """
        Read a line of user input with rudimentary line-editing, arrow navigation,
        and UTF-8 aware character handling. This intentionally keeps the feature
        set minimal but good enough for common SSH clients.

        Args:
            prompt: Text displayed before waiting for keystrokes.
            allow_empty: If False, blank submissions are ignored and the same
                prompt is redrawn in place.
            hidden: When True, the typed characters are replaced by ``*`` while
                editing (useful for passwords).
        """
        import codecs

        self.send(prompt, newline=False)
        buffer: list[str] = []
        cursor = 0
        decoder = codecs.getincrementaldecoder("utf-8")()
        escape_mode = False
        escape_buffer = ""

        def redraw() -> None:
            line = "".join(buffer)
            visible = "*" * len(line) if hidden else line
            self.send("\r", newline=False)
            self.send(prompt + visible, newline=False)
            self.send("\x1b[0K", newline=False)  # clear to end of line
            back = len(visible) - cursor
            if back > 0:
                self.send(f"\x1b[{back}D", newline=False)

        while True:
            data = self.channel.recv(1)
            if not data:
                break            
            
            byte = data[0]
            if byte in (0x0D, 0x0A):  # Enter
                if not allow_empty and not buffer:
                    redraw()
                    continue
                self.send("\r\n", newline=False)
                return "".join(buffer)
            if byte in (0x7F, 0x08):  # Backspace
                if cursor > 0:
                    cursor -= 1
                    buffer.pop(cursor)
                    redraw()
                continue
            if byte == 0x03:  # Ctrl+C
                self.send("^C", newline=True)
                raise KeyboardInterrupt()
            if byte == 0x04:  # Ctrl+D
                if not buffer:
                    return ""
                continue

            if escape_mode:
                escape_buffer += chr(byte)
                final_char = escape_buffer[-1]
                if final_char.isalpha() or final_char == "~":
                    seq = escape_buffer
                    escape_mode = False
                    escape_buffer = ""
                    if seq.startswith("["):
                        code = seq[1:]
                        if code == "D" and cursor > 0:
                            cursor -= 1
                            redraw()
                        elif code == "C" and cursor < len(buffer):
                            cursor += 1
                            redraw()
                        elif code in ("H", "1~"):
                            cursor = 0
                            redraw()
                        elif code in ("F", "4~"):
                            cursor = len(buffer)
                            redraw()
                        elif code == "3~" and cursor < len(buffer):
                            buffer.pop(cursor)
                            redraw()
                    continue
                continue

            if byte == 0x1B:  # ESC
                escape_mode = True
                escape_buffer = ""
                continue

            chunk = decoder.decode(bytes([byte]), final=False)
            if not chunk:
                continue

            for char in chunk:
                buffer.insert(cursor, char)
                cursor += 1
                redraw()

        return "".join(buffer)

    def drain_input_buffer(self) -> None:
        """Drop any pending keystrokes from the SSH channel."""
        channel = self.channel
        if not hasattr(channel, "recv_ready"):
            return
        while True:
            try:
                if not channel.recv_ready():
                    break
                channel.recv(1024)
            except Exception:
                break


class _SessionConsoleFile(TextIOBase):
    """Adapter so Rich can stream directly to the SSH channel."""

    def __init__(self, session: TermlitSession):
        super().__init__()
        self.session = session

    def write(self, s: str) -> int:  # type: ignore[override]
        if not s:
            return 0
        self.session.send(s, newline=False)
        return len(s)

    def writable(self) -> bool:  # type: ignore[override]
        return True

    def isatty(self) -> bool:  # type: ignore[override]
        return True

    def flush(self) -> None:  # type: ignore[override]
        return


class SpinnerContext:
    """Rich-powered spinner that mirrors Console.status behaviour."""

    def __init__(
        self,
        session: TermlitSession,
        spinner: str,
        text: str,
        persist: bool,
        lock_input: bool,
    ):
        self.session = session
        self.spinner = spinner
        self.text = text
        self.persist = persist
        self.lock_input = lock_input
        self._console = Console(
            file=_SessionConsoleFile(session),
            force_terminal=True,
            force_interactive=True,
            color_system="truecolor",
        )
        self._status_cm = None
        self._stop = threading.Event()
        self._drain_thread: Optional[threading.Thread] = None

    def __enter__(self):
        self._stop.clear()
        self._status_cm = self._console.status(self.text, spinner=self.spinner)
        self._status_cm.__enter__()
        if self.lock_input:
            self._drain_thread = threading.Thread(target=self._drain_loop, daemon=True)
            self._drain_thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop.set()
        if self._drain_thread:
            self._drain_thread.join(timeout=0.2)
        if self.lock_input:
            # Drop any bytes that arrived between the last drain and exit.
            self.session.drain_input_buffer()
        if self._status_cm:
            self._status_cm.__exit__(exc_type, exc, tb)

        if self.persist:
            if exc_type:
                self._console.print(f"[bold red]✗[/bold red] {self.text}")
            else:
                self._console.print(f"[bold green]✓[/bold green] {self.text}")
            self.session.send("")
        else:
            self.session.send("\r\x1b[0K", newline=False)
        if exc_type:
            self.session.send(f"[ERROR] {exc}", newline=True)
        return False

    def _drain_loop(self) -> None:
        while not self._stop.is_set():
            self.session.drain_input_buffer()
            time.sleep(0.05)


def welcome(
    title: str,
    subtitle: Optional[str] = None,
    description: Optional[str] = None,
) -> None:
    """Render a Rich welcome panel for the current session."""
    session = _current_session()
    console = Console(file=StringIO(), force_terminal=True, width=70)
    text = Text()
    text.append(title, style="bold green")
    if subtitle:
        text.append(f"\n{subtitle}", style="cyan")
    if description:
        text.append(f"\n\n{description}", style="white")

    panel = Panel(text, title="Termlit", border_style="bright_blue")
    console.print(panel)
    session.send(console.file.getvalue(), newline=False)


def input(
    prompt: str,
    *,
    allow_empty: bool = False,
    hidden: bool = False,
) -> str:
    """
    Request a line of user input.

    Args:
        prompt: Text shown before waiting for input.
        allow_empty: Whether to accept an empty submission (default False).
        hidden: Mask typed characters (for passwords).
    """
    session = _current_session()
    return session.receive_line(prompt, allow_empty=allow_empty, hidden=hidden)


def write(message: object) -> None:
    """Write plain text output to the terminal."""
    session = _current_session()
    session.send(str(message))


def goodbye(message: object = "再見！") -> None:
    """Close the session with a friendly farewell."""
    session = _current_session()
    session.send(str(message))


def spinner(
    name: str = "dots",
    text: str = "Loading...",
    *,
    persist: bool = False,
    lock_input: bool = True,
) -> SpinnerContext:
    """
    Return a context manager that streams a Rich spinner until the block exits.

    Args:
        name: Rich spinner preset name.
        text: Status text shown next to the spinner.
        persist: Keep the final ✓/✗ line instead of clearing it.
        lock_input: Drain user keystrokes while the spinner is running so nothing
            can be typed ahead of the next prompt.

    Example:
        with termlit.spinner("dots", "Loading...", lock_input=True):
            ...
    """
    session = _current_session()
    return SpinnerContext(session, name, text, persist, lock_input)


def post(
    url: str,
    *,
    header: Optional[Dict[str, str] | str] = None,
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, str] | str] = None,
    json: Optional[Dict[str, str]] = None,
    timeout: int = 10,
    log: bool = True,
) -> requests.Response:
    """
    Convenience wrapper around ``requests.post`` that also mirrors the toolkit
    API from the user's sample snippet.
    """
    session = _current_session()
    if headers and header:
        raise ValueError("Use either 'header' or 'headers', not both.")

    resolved_headers: Dict[str, str] = {}
    chosen_header = headers if headers is not None else header
    if isinstance(chosen_header, str):
        resolved_headers["Authorization"] = chosen_header
    elif isinstance(chosen_header, dict):
        resolved_headers = dict(chosen_header)

    response = requests.post(
        url,
        headers=resolved_headers,  # type: ignore[arg-type]
        data=data,
        json=json,
        timeout=timeout,
    )
    if log:
        summary = (
            f"POST {url} -> {response.status_code} "
            f"({len(response.content)} bytes)"
        )
        session.send(summary)
    return response
