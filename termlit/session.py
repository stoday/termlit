"""
Session level helpers that are exposed as the public API.

Each incoming SSH client receives its own session instance that tracks the
underlying Paramiko channel plus some metadata. The public helper functions in
this module proxy to the session stored in thread-local storage so the user
code can simply import `termlit` and call `welcome`, `input`, etc.
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from functools import partial
from io import StringIO, TextIOBase
from pathlib import Path
import threading
import time
from typing import Dict, Iterable, List, Optional, TYPE_CHECKING, Union

import requests
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

if TYPE_CHECKING:  # pragma: no cover - only used for typing
    import paramiko
    from http.server import ThreadingHTTPServer


class SessionNotReady(RuntimeError):
    """Raised when a public helper is called outside of an active session."""


_session_local: threading.local = threading.local()

UPLOAD_DIR_ENV = "TERMLIT_UPLOAD_DIR"
# DEFAULT_UPLOAD_DIRNAME = "upload_files"
DEFAULT_UPLOAD_DIRNAME = "."
DOWNLOAD_HOST_ENV = "TERMLIT_DOWNLOAD_HOST"
DOWNLOAD_PORT_ENV = "TERMLIT_DOWNLOAD_PORT"
DOWNLOAD_USER_ENV = "TERMLIT_DOWNLOAD_USER"
HTTP_SERVER_PORT_ENV = "TERMLIT_HTTP_PORT"
DEFAULT_SSH_PORT = 2222
DEFAULT_HTTP_PORT = 8765

PathInput = Union[str, os.PathLike[str], Path]
_http_server_lock = threading.Lock()
_http_server_info: Optional["_HTTPServerInfo"] = None


@dataclass
class _HTTPServerInfo:
    directory: Path
    port: int
    server: "ThreadingHTTPServer"
    thread: threading.Thread


def _current_session() -> "TermlitSession":
    session: Optional["TermlitSession"] = getattr(_session_local, "session", None)
    if session is None:
        raise SessionNotReady(
            "No active Termlit session. The helper functions can only be used "
            "when a session is running inside `termlit run <script.py>` or "
            "`termlit --local <script.py>`."
        )
    return session


def bind_session(session: "TermlitSession") -> None:
    """Attach a session to the current thread."""
    _session_local.session = session


def unbind_session() -> None:
    """Remove the session from the current thread."""
    if hasattr(_session_local, "session"):
        delattr(_session_local, "session")


def _resolve_upload_dir(custom: Optional[PathInput] = None) -> Path:
    if custom is not None:
        return Path(custom).expanduser().resolve()
    env_value = os.environ.get(UPLOAD_DIR_ENV)
    if env_value:
        return Path(env_value).expanduser().resolve()
    return (Path.cwd() / DEFAULT_UPLOAD_DIRNAME).resolve()


def _normalise_path_inputs(
    value: Union[PathInput, Iterable[PathInput]]
) -> List[Path]:
    if isinstance(value, (str, Path)) or isinstance(value, os.PathLike):
        return [Path(value)]
    try:
        iterator = iter(value)  # type: ignore[arg-type]
    except TypeError as exc:  # pragma: no cover - defensive
        raise TypeError(
            "Expected a path string or an iterable of paths."
        ) from exc
    items: List[Path] = []
    for item in iterator:
        if isinstance(item, (str, Path)) or isinstance(item, os.PathLike):
            items.append(Path(item))
            continue
        raise TypeError(f"Unsupported path type: {type(item)!r}")
    return items


RemoteInput = Union[str, os.PathLike[str], Path]


def _normalise_remote_paths(value: Union[RemoteInput, Iterable[RemoteInput]]) -> List[str]:
    def _coerce(item: RemoteInput) -> Optional[str]:
        text = str(item).strip()
        return text or None

    if isinstance(value, (str, Path)) or isinstance(value, os.PathLike):
        cleaned = _coerce(value)
        return [cleaned] if cleaned else []
    items: List[str] = []
    for item in value:
        if isinstance(item, (str, Path)) or isinstance(item, os.PathLike):
            cleaned = _coerce(item)
            if cleaned:
                items.append(cleaned)
            continue
        raise TypeError(f"Unsupported path type: {type(item)!r}")
    return items


def _prefix_remote_paths(
    paths: List[str], source_dir: Optional[PathInput]
) -> List[str]:
    if source_dir is None:
        return paths

    base = Path(source_dir).expanduser()
    if not base.is_absolute():
        base = (Path.cwd() / base).resolve()
    else:
        base = base.resolve()

    result: List[str] = []
    for raw in paths:
        candidate = Path(raw)
        if candidate.is_absolute():
            result.append(str(candidate))
        else:
            result.append(str((base / candidate).resolve()))
    return result


def _resolve_source_path(raw_path: Path) -> Path:
    candidate = raw_path.expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    candidate = candidate.resolve()
    if not candidate.exists():
        raise FileNotFoundError(candidate)
    if not candidate.is_file():
        raise IsADirectoryError(f"{candidate} is not a file")
    return candidate


def _resolve_existing_file(path_value: str) -> Path:
    candidate = Path(path_value).expanduser()
    if not candidate.is_absolute():
        candidate = Path.cwd() / candidate
    candidate = candidate.resolve()
    if not candidate.exists():
        raise FileNotFoundError(candidate)
    if not candidate.is_file():
        raise IsADirectoryError(f"{candidate} is not a file")
    return candidate


def _unique_destination(dest_dir: Path, desired_name: str) -> Path:
    dest_path = dest_dir / desired_name
    stem = dest_path.stem
    suffix = dest_path.suffix
    counter = 1
    while dest_path.exists():
        dest_path = dest_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    return dest_path


def _format_size(num_bytes: int) -> str:
    if num_bytes >= 1024 * 1024:
        return f"{num_bytes / (1024 * 1024):.1f} MB"
    if num_bytes >= 1024:
        return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes} B"


def _copy_with_progress(
    session: "TermlitSession",
    source_path: Path,
    dest_path: Path,
    show_progress: bool,
    chunk_size: int = 64 * 1024,
) -> None:
    if not show_progress:
        shutil.copy2(source_path, dest_path)
        return

    total = source_path.stat().st_size
    copied = 0
    last_percent = -1
    with open(source_path, "rb") as src, open(dest_path, "wb") as dst:
        while True:
            time.sleep(0.1)  # throttle updates for visibility
            chunk = src.read(chunk_size)
            if not chunk:
                break
            dst.write(chunk)
            copied += len(chunk)
            percent = 100 if total == 0 else int((copied / total) * 100)
            if percent != last_percent:
                session.send(
                    f"\r[UPLOAD] {source_path.name} -> {dest_path.name} {percent:3d}%",
                    newline=False,
                )
                last_percent = percent
    shutil.copystat(source_path, dest_path, follow_symlinks=True)
    session.send("", newline=True)


def _resolve_download_endpoint(session: "TermlitSession") -> tuple[str, int]:
    host = os.environ.get(DOWNLOAD_HOST_ENV)
    port_env = os.environ.get(DOWNLOAD_PORT_ENV)
    port: int = DEFAULT_SSH_PORT
    if port_env and port_env.isdigit():
        port = int(port_env)

    if host:
        return host, port

    try:
        transport = session.channel.get_transport()
        if transport and hasattr(transport, "sock"):
            sockname = transport.sock.getsockname()
            if sockname and isinstance(sockname, tuple):
                host = sockname[0] or host
                port = sockname[1] or port
    except Exception:
        pass

    return host or "<server-ip>", port


def _ensure_http_server(directory: Path, preferred_port: Optional[int] = None) -> int:
    global _http_server_info
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    desired_port = preferred_port
    if desired_port is None:
        env_port = os.environ.get(HTTP_SERVER_PORT_ENV)
        if env_port and env_port.isdigit():
            desired_port = int(env_port)
    if desired_port is None:
        desired_port = DEFAULT_HTTP_PORT

    class QuietHandler(SimpleHTTPRequestHandler):
        def log_message(self, format, *args):  # pragma: no cover - noise suppression
            return

    handler = partial(QuietHandler, directory=str(directory))

    with _http_server_lock:
        if (
            _http_server_info
            and _http_server_info.directory == directory
            and _http_server_info.server
        ):
            return _http_server_info.port

        if _http_server_info:
            try:
                _http_server_info.server.shutdown()
                _http_server_info.server.server_close()
            except Exception:
                pass
            _http_server_info = None

        attempt_port = desired_port
        server: Optional[ThreadingHTTPServer] = None

        while True:
            try:
                server = ThreadingHTTPServer(("0.0.0.0", attempt_port), handler)
                break
            except OSError:
                if attempt_port == 0:
                    raise
                attempt_port = 0  # let OS choose

        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        actual_port = server.server_address[1]
        _http_server_info = _HTTPServerInfo(
            directory=directory,
            port=actual_port,
            server=server,
            thread=thread,
        )
        return actual_port


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


@dataclass
class LocalSession:
    """Local terminal session backed by stdin/stdout."""

    username: str = "local"

    def send(self, message: str = "", newline: bool = True) -> None:
        if newline and not message.endswith("\n"):
            message += "\n"
        try:
            sys.stdout.write(message)
            sys.stdout.flush()
        except Exception:
            pass

    def receive_line(
        self,
        prompt: str = "",
        *,
        allow_empty: bool = True,
        hidden: bool = False,
    ) -> str:
        import builtins
        import getpass

        while True:
            try:
                if hidden:
                    line = getpass.getpass(prompt)
                else:
                    line = builtins.input(prompt)
            except EOFError:
                return ""
            if line or allow_empty:
                return line

    def drain_input_buffer(self) -> None:
        return


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
    panel_title: str = "Termlit",
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

    panel = Panel(text, title=panel_title, border_style="bright_blue")
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


def input_multiline(
    prompt: str,
    *,
    end_marker: str = ".",
    allow_empty: bool = False,
    hidden: bool = False,
) -> str:
    """
    Read multiple lines of input from the user until a line equal to
    ``end_marker`` is entered on its own line.

    Note: SSH terminal clients do not send modifier key metadata (for example
    Shift+Enter) as a distinct code, so it's not possible to reliably detect
    Shift+Enter over an SSH session. This helper provides a simple and
    portable alternative: the user types multiple lines and then enters the
    configured ``end_marker`` alone on a line to finish.

    Args:
        prompt: Initial prompt shown to the user.
        end_marker: A single-line sentinel that ends multiline input (default: `.`).
        allow_empty: Passed to the underlying line reader for each line.
        hidden: If True, each input line will be masked (rare for multiline usage).

    Returns:
        A single string containing the collected lines joined with ``\n``.
    """
    session = _current_session()
    session.send(f"{prompt} (end with a line containing only '{end_marker}')")
    lines: list[str] = []
    while True:
        line = session.receive_line(
            "", allow_empty=allow_empty, hidden=hidden
        )
        if line == end_marker:
            break
        lines.append(line)
    return "\n".join(lines)


def _iter_stream_chunks(message: object) -> Iterable[object]:
    if isinstance(message, (str, bytes)):
        yield message
        return
    try:
        iterator = iter(message)  # type: ignore[arg-type]
    except TypeError as exc:  # pragma: no cover - defensive
        raise TypeError(
            "stream=True expects an iterable of chunks or a string/bytes object."
        ) from exc
    for chunk in iterator:
        yield chunk


def write(message: object, *, stream: bool = False) -> None:
    """Write plain text output to the terminal.

    Args:
        message: Text (or iterable of text chunks) to send.
        stream: When True, treat ``message`` as an iterable and forward each
            chunk as soon as it is produced. Strings/bytes are always handled
            as single chunks to avoid per-character writes.
    """
    session = _current_session()
    if not stream:
        session.send(str(message))
        return

    last_chunk: Optional[str] = None
    for chunk in _iter_stream_chunks(message):
        if isinstance(chunk, bytes):
            text = chunk.decode("utf-8", errors="ignore")
        else:
            text = str(chunk)
        session.send(text, newline=False)
        last_chunk = text

    if last_chunk is None or not last_chunk.endswith("\n"):
        session.send("")


def goodbye(message: object = "Goodbye！") -> None:
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
    
    try:
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
    except requests.RequestException as e:
        session.send(f"[ERROR] {e}", newline=True)
        raise
    return response


def upload_files(
    files: Union[PathInput, Iterable[PathInput], None] = None,
    *,
    destination_dir: Optional[PathInput] = None,
    log: bool = True,
    file_or_files: Union[PathInput, Iterable[PathInput], None] = None,
    show_progress: bool = False,
    replace: bool = False,
) -> List[Path]:
    """
    Copy one or more files into the Termlit ``upload_files`` directory.

    Args:
        files: Path string, Path object, or iterable of paths to copy.
        file_or_files: Alias for ``files`` to support earlier documentation.
        destination_dir: Override the default upload directory. If omitted,
            ``$TERMLIT_UPLOAD_DIR`` or ``./upload_files`` is used.
        log: Whether to emit a short status line for each uploaded file.
        show_progress: Stream simple percentage updates (per file) to the SSH session.
        replace: When ``True`` reuse the original filenames even if they already
            exist (overwriting the previous copy). Defaults to ``False`` which
            auto-appends suffixes to avoid collisions.

    Returns:
        A list of paths representing the copied files on the server.
    """
    session = _current_session()
    source_arg: Union[PathInput, Iterable[PathInput], None] = files
    if source_arg is None:
        source_arg = file_or_files
    elif file_or_files is not None:
        raise ValueError("Use either 'files' or 'file_or_files', not both.")
    if source_arg is None:
        raise ValueError("No files provided for upload.")

    paths = _normalise_path_inputs(source_arg)
    dest_dir = _resolve_upload_dir(destination_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)

    uploaded: List[Path] = []
    for raw in paths:
        source_path = _resolve_source_path(raw)
        if replace:
            dest_path = dest_dir / source_path.name
        else:
            dest_path = _unique_destination(dest_dir, source_path.name)

        if dest_path.exists() and source_path.resolve() == dest_path.resolve():
            if log:
                size_text = _format_size(source_path.stat().st_size)
                session.send(
                    f"[UPLOAD] {source_path} is already located at {dest_path} "
                    f"({size_text}) - skipped self-copy."
                )
            uploaded.append(dest_path)
            continue

        _copy_with_progress(session, source_path, dest_path, show_progress)
        uploaded.append(dest_path)
        if log:
            size_text = _format_size(dest_path.stat().st_size)
            session.send(f"[UPLOAD] {source_path} -> {dest_path} ({size_text})")
    return uploaded


def upload_file(
    file_or_files: Union[PathInput, Iterable[PathInput]],
    *,
    destination_dir: Optional[PathInput] = None,
    log: bool = True,
    show_progress: bool = False,
    replace: bool = False,
) -> Union[Path, List[Path]]:
    """
    Convenience wrapper around :func:`upload_files`.

    Accepts either a single file path or an iterable of paths. When multiple
    paths are provided the returned value matches :func:`upload_files`.
    Set ``show_progress=True`` to stream percentage updates for each copy.
    Pass ``replace=True`` to overwrite files with identical names instead of
    auto-generating unique filenames.
    
    returns:
        A single Path if a single file was provided, or a list of Paths
        if multiple files were provided.
    """
    uploaded = upload_files(
        file_or_files,
        destination_dir=destination_dir,
        log=log,
        show_progress=show_progress,
        replace=replace,
    )
    if len(uploaded) == 1:
        return uploaded[0]
    return uploaded


def download_cmd(
    file_or_files: Union[RemoteInput, Iterable[RemoteInput]],
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    source_dir: Optional[PathInput] = None,
    destination: str = ".",
    username: Optional[str] = None,
    type: str = "http",
) -> str:
    """
    Return scp commands that the user can run locally to download files or download URLs
    if using HTTP mode.

    Args:
        file_or_files: Path string or iterable of paths located on the server.
        host: Override the server host in the generated commands.
        port: Override the SSH/HTTP port (default derives from the running server).
        source_dir: Optional folder prefix on the server. Relative input paths
            will be treated as located under this directory.
        destination: Local directory placeholder shown in the scp command.
        username: Override the SSH username (scp mode). Defaults to the current session
            user or the ``TERMLIT_DOWNLOAD_USER`` environment variable.
        type: ``"scp"`` (default) 產生 scp 指令； ``"http"`` 則在指定資料夾啟動
            ``http.server`` 並回傳可點擊的下載 URL。

    Returns:
        A single command string if only one path is provided, otherwise multiple
        commands separated by newlines.
    """
    session = _current_session()
    download_type = (type or "scp").strip().lower()
    if download_type not in {"scp", "http"}:
        raise ValueError("download_cmd type must be either 'scp' or 'http'.")

    paths = _normalise_remote_paths(file_or_files)
    if not paths:
        raise ValueError("No file path provided for download command.")
    combined_paths = _prefix_remote_paths(paths, source_dir)

    if download_type == "scp":
        resolved_host, resolved_port = _resolve_download_endpoint(session)
        host = host or resolved_host
        if port is None:
            port_env = os.environ.get(DOWNLOAD_PORT_ENV)
            if port_env and port_env.isdigit():
                port = int(port_env)
            else:
                port = resolved_port

        resolved_user = (
            username
            or os.environ.get(DOWNLOAD_USER_ENV)
            or session.username
            or "admin"
        )

        commands: List[str] = []
        for path in combined_paths:
            commands.append(
                f"scp -P {port} {resolved_user}@{host}:{path} {destination}"
            )
        return commands[0] if len(commands) == 1 else "\n".join(commands)

    # HTTP mode
    local_files = [_resolve_existing_file(p) for p in combined_paths]
    parents = {f.parent for f in local_files}
    if len(parents) != 1:
        raise ValueError("HTTP 下載僅支援同一資料夾內的檔案，請先集中到同一Path。")
    directory = parents.pop()
    port_value = port
    http_port = _ensure_http_server(directory, port_value)
    resolved_host, _ = _resolve_download_endpoint(session)
    host = host or resolved_host

    urls = [f"http://{host}:{http_port}/{file.name}" for file in local_files]
    return "\n".join(urls)
