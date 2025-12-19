"""
Runtime utilities for serving Termlit apps over SSH.
"""

from __future__ import annotations

import io
import multiprocessing
import os
import runpy
import socket
import sys
import threading
import time
import traceback
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Protocol

import paramiko

from .session import LocalSession, TermlitSession, bind_session, unbind_session


DEFAULT_USERS = {"admin": "password123"}
DEFAULT_KEY_PATH = Path(".termlit_host_key.pem")


class SessionRunner(Protocol):
    """Protocol describing an object that can produce a Termlit session."""

    def run(self) -> None:
        ...


class CallableRunner:
    """Wrap any zero-argument callable so it can be executed per session."""

    def __init__(self, fn: Callable[[], None]):
        self._fn = fn

    def run(self) -> None:
        self._fn()


class ScriptRunner:
    """Executes a Python script on each new session."""

    def __init__(self, script_path: Path, argv: Optional[Iterable[str]] = None):
        self.script_path = Path(script_path).resolve()
        self.argv = [str(self.script_path)] + (list(argv) if argv else [])

    def run(self) -> None:
        if not self.script_path.exists():
            raise FileNotFoundError(self.script_path)

        script_dir = str(self.script_path.parent)
        added_to_path = False
        if script_dir not in sys.path:
            sys.path.insert(0, script_dir)
            added_to_path = True

        old_argv = sys.argv
        sys.argv = self.argv.copy()
        os.environ.setdefault("TERMLIT_ACTIVE", "1")
        try:
            runpy.run_path(str(self.script_path), run_name="__main__")
        finally:
            sys.argv = old_argv
            if added_to_path:
                try:
                    sys.path.remove(script_dir)
                except ValueError:
                    pass


class _SessionStream(io.TextIOBase):
    """Redirects stdout/stderr to the active session."""

    def __init__(self, session: TermlitSession):
        super().__init__()
        self.session = session

    def write(self, s: str) -> int:  # type: ignore[override]
        if not s:
            return 0
        self.session.send(s, newline=False)
        return len(s)

    def readable(self) -> bool:
        return False

    def writable(self) -> bool:
        return True

    def flush(self) -> None:  # type: ignore[override]
        return


@contextmanager
def _redirect_stdio(session: TermlitSession):
    original_out, original_err = sys.stdout, sys.stderr
    stream = _SessionStream(session)
    sys.stdout = stream
    sys.stderr = stream
    try:
        yield
    finally:
        sys.stdout = original_out
        sys.stderr = original_err


class _SSHInterface(paramiko.ServerInterface):
    """Minimal Paramiko server interface with password authentication."""

    def __init__(self, users: Optional[Dict[str, str]], auth_mode: str = "ssh"):
        self._users = users or {}
        self._auth_mode = auth_mode
        self.username: Optional[str] = None

    def check_auth_none(self, username):
        if self._auth_mode == "none":
            self.username = username or "anonymous"
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_auth_password(self, username, password):
        if self._auth_mode == "none":
            self.username = username or "anonymous"
            return paramiko.AUTH_SUCCESSFUL

        if not self._users:
            self.username = username or "anonymous"
            return paramiko.AUTH_SUCCESSFUL

        if username in self._users and self._users[username] == password:
            self.username = username
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_channel_request(self, kind, chanid):
        if kind == "session":
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def check_channel_shell_request(self, channel):
        return True

    def check_channel_pty_request(
        self,
        channel,
        term,
        width,
        height,
        pixelwidth,
        pixelheight,
        modes,
    ):
        return True


class TermlitSSHServer:
    """SSH server that spins a new Termlit session per client."""

    def __init__(
        self,
        *,
        host: str = "0.0.0.0",
        port: int = 2222,
        runner: SessionRunner,
        users: Optional[Dict[str, str]] = None,
        auth_mode: str = "ssh",
        key_path: Path = DEFAULT_KEY_PATH,
    ):
        self.host = host
        self.port = port
        self.runner = runner
        self.auth_mode = auth_mode
        if auth_mode == "ssh":
            self.users = users.copy() if users is not None else DEFAULT_USERS.copy()
        else:
            self.users = {}
        self.key_path = key_path
        self.server_key = self._load_or_create_key()
        self._socket: Optional[socket.socket] = None
        self._stop = threading.Event()

    def _load_or_create_key(self) -> paramiko.RSAKey:
        key_path = self.key_path
        try:
            if key_path.exists():
                return paramiko.RSAKey.from_private_key_file(str(key_path))
            if key_path.parent and not key_path.parent.exists():
                key_path.parent.mkdir(parents=True, exist_ok=True)
            key = paramiko.RSAKey.generate(2048)
            key.write_private_key_file(str(key_path))
            return key
        except Exception:
            # Fall back to an in-memory key if disk operations fail.
            print("[Termlit] Cannot access key file, using temporary key.")
            return paramiko.RSAKey.generate(2048)

    def serve_forever(self) -> None:
        """Start the SSH server and block forever."""
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.bind((self.host, self.port))
        self._socket.listen(100)
        self._socket.settimeout(0.5)

        print(f"[Termlit] SSH server listening on {self.host}:{self.port}")
        if self.auth_mode == "none":
            print("[Termlit] Passwordless login enabled (--auth none).")
        elif self.users:
            pw_info = ", ".join(f"{u}/{p}" for u, p in self.users.items())
            print(f"[Termlit] Available logins: {pw_info}")
        else:
            print("[Termlit] Anonymous login enabled (any username/password).")

        try:
            while not self._stop.is_set():
                try:
                    client, address = self._socket.accept()
                except socket.timeout:
                    continue
                except OSError:
                    if self._stop.is_set():
                        break
                    raise

                thread = threading.Thread(
                    target=self._handle_client, args=(client, address), daemon=True
                )
                thread.start()
        except KeyboardInterrupt:
            print("\n[Termlit] Stopping server...")
        finally:
            self._stop.set()
            self._close_socket()

    def _handle_client(self, client_socket, address) -> None:  # pragma: no cover
        transport = None
        channel = None
        try:
            transport = paramiko.Transport(client_socket)
            transport.add_server_key(self.server_key)
            interface = _SSHInterface(self.users, auth_mode=self.auth_mode)
            transport.start_server(server=interface)
            channel = transport.accept(30)
            if channel is None:
                return

            username = interface.username or "anonymous"
            print(f"[Termlit] Session started for {username} from {address}")
            session = TermlitSession(channel=channel, username=username)

            bind_session(session)
            with _redirect_stdio(session):
                try:
                    self.runner.run()
                except KeyboardInterrupt:
                    session.send("[Termlit] Session cancelled by user.")
        except Exception as exc:
            if channel:
                channel.send(
                    f"\r\n[Termlit] Error: {exc}\r\n".encode("utf-8", errors="ignore")
                )
            traceback.print_exception(type(exc), exc, exc.__traceback__)
        finally:
            unbind_session()
            try:
                if channel and not channel.closed:
                    channel.close()
            finally:
                if transport:
                    transport.close()
                client_socket.close()
        print(f"[Termlit] Session closed for {address}")

    def _close_socket(self) -> None:
        """Close the listening socket if it is open."""
        if self._socket:
            try:
                self._socket.close()
            finally:
                self._socket = None


def run(
    app: Callable[[], None],
    *,
    host: str = "0.0.0.0",
    port: int = 2222,
    users: Optional[Dict[str, str]] = None,
    auth_mode: str = "ssh",
) -> None:
    """Start the SSH server with an in-memory callable app."""
    runner = CallableRunner(app)
    server = TermlitSSHServer(
        host=host,
        port=port,
        runner=runner,
        users=users,
        auth_mode=auth_mode,
    )
    server.serve_forever()


def serve_script(
    script_path: Path,
    *,
    host: str = "0.0.0.0",
    port: int = 2222,
    users: Optional[Dict[str, str]] = None,
    auth_mode: str = "ssh",
) -> None:
    """Start the SSH server using a script file as the app entry."""
    runner = ScriptRunner(script_path)
    server = TermlitSSHServer(
        host=host,
        port=port,
        runner=runner,
        users=users,
        auth_mode=auth_mode,
    )
    server.serve_forever()


def run_local_script(script_path: Path) -> None:
    """Run a Termlit script directly on the local terminal."""
    runner = ScriptRunner(script_path)
    username = (
        os.environ.get("USER")
        or os.environ.get("USERNAME")
        or os.environ.get("LOGNAME")
        or "local"
    )
    session = LocalSession(username=username)
    bind_session(session)
    try:
        try:
            runner.run()
        except KeyboardInterrupt:
            session.send("[Termlit] Session cancelled by user.")
    finally:
        unbind_session()


def serve_script_with_reloader(
    script_path: Path,
    *,
    host: str = "0.0.0.0",
    port: int = 2222,
    users: Optional[Dict[str, str]] = None,
    auth_mode: str = "ssh",
    poll_interval: float = 0.5,
) -> None:
    """Start the SSH server and restart it whenever the script file changes."""

    script_path = Path(script_path).resolve()
    current_mtime = _script_mtime(script_path)
    print(f"[Termlit] Auto-reload enabled for {script_path}")

    process: Optional[multiprocessing.Process] = _spawn_script_process(
        script_path, host=host, port=port, users=users, auth_mode=auth_mode
    )

    try:
        while True:
            time.sleep(poll_interval)
            new_mtime = _script_mtime(script_path)
            if new_mtime != current_mtime:
                current_mtime = new_mtime
                print("[Termlit] Detected changes. Reloading...")
                process = _restart_process(
                    process,
                    script_path,
                    host=host,
                    port=port,
                    users=users,
                    auth_mode=auth_mode,
                )
                continue

            if process is None:
                continue

            if not process.is_alive():
                exit_code = process.exitcode or 0
                if exit_code == 0:
                    return
                print(
                    "[Termlit] Server exited with errors. Waiting for file changes to restart..."
                )
                process.join()
                process = None
    except KeyboardInterrupt:
        print("\n[Termlit] Reload loop interrupted. Shutting down...")
    finally:
        if process:
            if process.is_alive():
                process.terminate()
            process.join()


def _script_mtime(script_path: Path) -> int:
    try:
        return script_path.stat().st_mtime_ns
    except FileNotFoundError:
        return 0


def _spawn_script_process(
    script_path: Path,
    *,
    host: str,
    port: int,
    users: Optional[Dict[str, str]],
    auth_mode: str,
) -> multiprocessing.Process:
    process = multiprocessing.Process(
        target=_serve_script_subprocess,
        args=(str(script_path), host, port, users, auth_mode),
        daemon=True,
    )
    process.start()
    return process


def _restart_process(
    process: Optional[multiprocessing.Process],
    script_path: Path,
    *,
    host: str,
    port: int,
    users: Optional[Dict[str, str]],
    auth_mode: str,
) -> multiprocessing.Process:
    if process:
        if process.is_alive():
            process.terminate()
        process.join()
    return _spawn_script_process(
        script_path, host=host, port=port, users=users, auth_mode=auth_mode
    )


def _serve_script_subprocess(
    script_path: str,
    host: str,
    port: int,
    users: Optional[Dict[str, str]],
    auth_mode: str,
) -> None:
    serve_script(
        Path(script_path),
        host=host,
        port=port,
        users=users,
        auth_mode=auth_mode,
    )
