# termlit
Termlit is a small Python tool that provides an SSH server interface.
It makes it easy to expose interactive applications over SSH — for example,
to host AI-powered conversational services that users can connect to with an SSH client.

## Features
- SSH server with ready-to-use credentials (or anonymous mode)
- Built-in Rich welcome panels and simple text helpers
- Rich-powered spinners that lock user input while background work is running
- Request/response helpers (`termlit.post`) powered by `requests`
- Password-masked input via `termlit.input(..., hidden=True)`
- Session-scoped stdout redirection so `print()` just works
- Upload helpers (`termlit.upload_file(s)`) that copy generated files into an
  `upload_files/` directory so you can retrieve them easily
- Download helpers (`termlit.download_cmd`) that generate ready-to-run scp
  commands or temporary HTTP links for your end users

## Installation

Two common installation methods are shown below:

- From PyPI (recommended for end users):

```bash
python -m pip install termlit
```

- From GitHub (editable / development install):

```bash
git clone https://github.com/stoday/termlit.git
cd termlit
python -m pip install -e .
```

The editable install makes it easy to modify code and test changes locally.

## Quick start
1. Install the package (editable mode during development is fine):
   ```bash
   pip install -e .
   ```

   or, if you prefer [uv](https://github.com/astral-sh/uv):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh  # install uv (once)
   uv pip install -e .
   ```
2. Create a script, e.g. `app.py`:
   ```python
   import termlit

   termlit.welcome(
       title="Welcome~",
       subtitle="version 1.0.0",
       description="This is a note",
   )

   while True:
       prompt = termlit.input("User question: ")
       if prompt.lower() in {"quit", "exit"}:
           termlit.goodbye("Goodbye! See you next time")
           break

       with termlit.spinner("dots", "Processing your question..."):
           response = termlit.post(
               url="https://httpbin.org/post",
               json={"question": prompt},
               log=False,  # Suppress automatic POST summary
           )

       termlit.write("Answer: " + str(response.json()))
   ```
    > `termlit.spinner` blocks input by default, so users cannot queue input while a background task is running.
    > By default `termlit.input` ignores empty input; allow empty input with `allow_empty=True`.
    > Use `termlit.input("input password: ", hidden=True)` when you need password input — the input will be masked with `*`.
3. Serve it over SSH:
   ```bash
   termlit run app.py --host 0.0.0.0 --port 2222 --reload
   ```
    > Add `--auth none` to allow passwordless login (the default is `--auth ssh`, which requires a password).
   Or run it locally without SSH:
   ```bash
   termlit run app.py --local
   ```
4. Connect from any SSH client (default credentials `admin/password123`):
   ```bash
   ssh admin@127.0.0.1 -p 2222
   ```

## Local mode
If you want to run a Termlit app without starting an SSH server, add `--local`:

```bash
termlit run app.py --local
```

Notes:
- Runs the app on your local terminal using stdin/stdout (no remote access).
- `--host`, `--port`, `--auth`, `--user`, and `--allow-anonymous` are ignored in local mode.
- Useful for quick iteration or single-user usage on the same machine.

## CLI flags
- `--user name=secret`: add/override login credentials (repeatable).
- `--auth {ssh,none}`: choose between password-protected (`ssh`) or passwordless (`none`) sessions.
- `--allow-anonymous`: accept any username/password combo.
- `--local`: run a script locally without starting an SSH server (use with `run`).
- `--reload`: watch the target script and restart the SSH server whenever it changes (development helper).
- `--host` / `--port`: where the SSH server listens.
- `--version`: display the installed Termlit version and exit.

## Streaming output
When you already have a generator/iterable that yields text chunks (for example,
tailing logs or chunked API responses), call `termlit.write(..., stream=True)`
to forward each chunk immediately without buffering:

```python
def stream_logs():
    for line in follow_log_file():
        yield line

termlit.write(stream_logs(), stream=True)
```
Strings/bytes are still treated as a single chunk, so you can safely switch the
flag on even when a function sometimes returns plain text and sometimes returns
an iterator.

## Programmatic usage
You can also embed Termlit inside a Python process:
```python
import termlit

def app():
    termlit.welcome("Inline app")
    termlit.write("Hello there!")
    termlit.goodbye()

if __name__ == "__main__":
    termlit.run(app, host="127.0.0.1", port=2222)
```
> To allow passwordless sessions, pass `auth_mode="none"` to `termlit.run`.

## Uploading files
Use the `upload_files`/`upload_file` helpers when your script needs to drop
artifacts (reports, logs, etc.) into a directory that you can fetch later:

```python
import termlit

# Copy a single file to ./upload_files (or $TERMLIT_UPLOAD_DIR) with progress
termlit.upload_files("build/output/report.pdf", show_progress=True)

# Copy multiple files and grab the resulting server-side paths
uploaded = termlit.upload_file(
    ["app.log", r"C:\temp\screenshot.png"],
    show_progress=True,
)
termlit.write("Saved files to:")
for path in uploaded:
    termlit.write(f" - {path}")

# Provide ready-to-run scp commands for the client
cmd = termlit.download_cmd(
    "report.pdf",
    source_dir="upload_files",
)
termlit.write("Run command locally to download:")
termlit.write(cmd)

# Or host a temporary HTTP download link
http_links = termlit.download_cmd(
    "report.pdf",
    source_dir="upload_files",
    type="http",
)
termlit.write("Or open in browser:")
termlit.write(http_links)
```

All files are copied into `upload_files/` relative to where `termlit run` was
executed (override via the `TERMLIT_UPLOAD_DIR` environment variable or the
``destination_dir`` argument). Pass `show_progress=True` to stream simple
percentage updates back to the SSH client while a file is being copied. Use
``replace=True`` when you want to overwrite same-named files instead of letting
Termlit append `_1`, `_2`, ... suffixes (the default collision-avoidance
behaviour). Use
`termlit.download_cmd(...)` to generate the scp command your users should run
locally, pass ``source_dir="upload_files"`` when you want to specify the hosting
folder, or set ``type="http"`` to spin up a temporary `http.server` over the
target folder. Set `TERMLIT_DOWNLOAD_HOST`, `TERMLIT_DOWNLOAD_PORT`,
`TERMLIT_DOWNLOAD_USER`, or `TERMLIT_HTTP_PORT` when the defaults are
insufficient.

## Downloading files
Once your script calls `termlit.upload_file(...)`, you have two convenient ways
to guide end users through downloading the artifacts:

1. **scp command** – Call `termlit.download_cmd("report.pdf", source_dir="upload_files")`
    to generate a string like `scp -P 2222 admin@<host>:/abs/path/report.pdf ./`.
    Give this command to your user to run locally. Adjust host/port/user via
    env vars `TERMLIT_DOWNLOAD_HOST`, `TERMLIT_DOWNLOAD_PORT`,
    `TERMLIT_DOWNLOAD_USER`, or override using `host=`, `port=`, `username=`,
    `destination=`.
2. **HTTP download** – Pass `type="http"`, for example
    `termlit.download_cmd("report.pdf", source_dir="upload_files", type="http")`.
    This starts a temporary `http.server` (default port `8765`, override with
    `TERMLIT_HTTP_PORT`) and returns a URL like `http://<host>:8765/report.pdf`.
    The user can download via a browser; server access logging is suppressed by
    default to avoid interfering with the SSH interface.

> The HTTP mode requires all target files to be in the same folder—collect
> them into `upload_files/` before generating a link. Remind users to stop the
> temporary HTTP server (restart the app or run a custom command) after
> downloading for security.

## Repository layout
- `termlit/session.py` – public helper implementations.
- `termlit/runtime.py` – SSH server + script runner.
- `termlit/cli.py` – command line interface (`termlit run`).
- `scripts/ssh_server_plain.py`, `scripts/telnet_server.py` – original demo servers (optional utilities; they call an external FastAPI backend that you must run yourself).
- `scripts/start_services.py` – helper script that starts the Telnet/SSH demos and forwards the `--fastapi-url` you provide.

Happy terminal building!

## Developer Overview

- `termlit/__init__.py`: Re-exports Termlit's public API (`welcome`,
    `input`, `upload_file`, etc.). It also loads version information and binds
    the thread-local session on import.
- `termlit/session.py`: The session implementation that backs all public
    helpers (UI, HTTP helpers, upload/download) and maintains the internal
    `_current_session` state.
- `termlit/runtime.py`: Starts and manages the SSH server and the script
    runner; provides a reload/watchdog flow via `serve_script_with_reloader`.
- `termlit/cli.py`: The CLI entrypoint for `termlit`; parses arguments for
    `termlit run`, manages authentication options, and invokes the runtime.
- `example_app.py`: An example app demonstrating how to build a Termlit flow,
    upload files, and interact with an HTTP API.
- `scripts/ssh_server_plain.py` / `scripts/telnet_server.py`: Legacy demo
    servers that showcase an interactive shell and optional integration with an
    external FastAPI backend.
- `scripts/start_services.py`: A convenience helper to start the Telnet/SSH
    demos and forward a common `--fastapi-url` to both services.
- `tests/`: Unit and integration tests; please add tests covering new helpers
    or runtime behavior when introducing features.
- `upload_files/`: The default location for server-side uploaded artifacts
    (override with `TERMLIT_UPLOAD_DIR`).
