# termlit
Termlit converts a plain Python script into an interactive SSH experience.  
Write terminal flows with `welcome`, `input`, and `post` helpers, then expose
them over SSH via `termlit run app.py`.

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
   > `termlit.spinner` blocks input by default, so users cannot queue input during wait.
   > By default `termlit.input` ignores empty input, allow with `allow_empty=True`。
   > 需要輸入Password時可使用 `termlit.input("input password: ", hidden=True)` for password input masked with `*`.
3. Serve it over SSH:
   ```bash
   termlit run app.py --host 0.0.0.0 --port 2222 --reload
   ```
   > Add `--auth none` 可讓使用者免Password登入（預設為 `--auth ssh` 需輸入Password）。
4. Connect from any SSH client (default credentials `admin/password123`):
   ```bash
   ssh admin@127.0.0.1 -p 2222
   ```

## CLI flags
- `--user name=secret`: add/override login credentials (repeatable).
- `--auth {ssh,none}`: choose between password-protected (`ssh`) or passwordless (`none`) sessions.
- `--allow-anonymous`: accept any username/password combo.
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
> 需要免Password體驗時, 可傳入 `auth_mode="none"` 給 `termlit.run`.

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

1. **scp 指令** – 呼叫 `termlit.download_cmd("report.pdf", source_dir="upload_files")`
   generates string like `scp -P 2222 admin@<host>:/abs/path/report.pdf ./`. Copy this
   command to user to run locally. Adjust host/port/user via env vars
   `TERMLIT_DOWNLOAD_HOST`, `TERMLIT_DOWNLOAD_PORT`, `TERMLIT_DOWNLOAD_USER`
   or override using `host=`, `port=`, `username=`,
   `destination=`。
2. **HTTP 下載** – 傳入 `type="http"`, e.g.
   `termlit.download_cmd("report.pdf", source_dir="upload_files", type="http")`, 
   starts `http.server` (default port `8765` use 
   `TERMLIT_HTTP_PORT` 覆寫）, 並回傳 `http://<host>:8765/report.pdf` URL.
   User downloads via browser; server access log is
   自動抑制, 避免干擾 SSH 介面。

> HTTP 模式要求所有檔案在同一個資料夾, 可將檔案集中到 `upload_files/`
> then generate link. Remind user to close temp HTTP server (restart app
> or custom cmd) for security.

## Repository layout
- `termlit/session.py` – public helper implementations.
- `termlit/runtime.py` – SSH server + script runner.
- `termlit/cli.py` – command line interface (`termlit run`).
- `scripts/ssh_server_plain.py`, `scripts/telnet_server.py` – original demo servers (optional utilities; they call an external FastAPI backend that you must run yourself).
- `scripts/start_services.py` – helper script that starts the Telnet/SSH demos and forwards the `--fastapi-url` you provide.

Happy terminal building!

## Developer Overview
- `termlit/__init__.py`: 集中 re-export Termlit 公開 API（welcome、input、upload_file...）, 也在匯入時載入版本資訊與 thread-local session 綁定。
- `termlit/session.py`: Session 層主程式, 實作所有對外 helper（UI、HTTP、上傳/下載等）, 並維護 `_current_session`, file copy, HTTP download service details.
- `termlit/runtime.py`: 啟動/管理 SSH 伺服器與 ScriptRunner, 並提供 `serve_script_with_reloader` watchdog flow; handles Paramiko server interface and stdout redirection.
- `termlit/cli.py`: `termlit` 指令的進入點, 解析 `termlit run` flags, manages auth settings and calls runtime.
- `example_app.py`: 內建範例, 展示如何建立 Termlit 流程、上傳檔案以及和 HTTP API 互動。
- `scripts/ssh_server_plain.py` / `scripts/telnet_server.py`: 較早期的互動式 demo 伺服器, 提供自建命令列介面並透過外部 FastAPI 後端提供應答。
- `scripts/start_services.py`: 方便一次啟動 telnet/ssh demo 並將 `--fastapi-url` to both.
- `tests/`: 單元/整合測試樣本；新增功能時請補上覆蓋相關 helper 或 runtime 的測試。
- `upload_files/`: 預設的伺服器端上傳輸出資料夾（可透過 `TERMLIT_UPLOAD_DIR` 覆寫）, 便於從本機取得 Termlit Session 中產生的檔案。
