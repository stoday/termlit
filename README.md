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
       prompt = termlit.input("使用者提問: ")
       if prompt.lower() in {"quit", "exit"}:
           termlit.goodbye("再見！期待下次")
           break

       with termlit.spinner("dots", "正在處理您的問題..."):
           response = termlit.post(
               url="https://httpbin.org/post",
               json={"question": prompt},
               log=False,  # 避免自動輸出 POST 摘要
           )

       termlit.write("回答: " + str(response.json()))
   ```
   > `termlit.spinner` 會預設鎖定輸入，因此使用者無法在等待期間排隊輸入任何字。
   > 預設情況下 `termlit.input` 會忽略空白輸入，若要允許可傳入 `allow_empty=True`。
   > 需要輸入密碼時可使用 `termlit.input("input password: ", hidden=True)` 來以 `*` 遮罩輸入。
3. Serve it over SSH:
   ```bash
   termlit run app.py --host 0.0.0.0 --port 2222 --reload
   ```
   > 加上 `--auth none` 可讓使用者免密碼登入（預設為 `--auth ssh` 需輸入密碼）。
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
> 需要免密碼體驗時，可傳入 `auth_mode="none"` 給 `termlit.run`.

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
termlit.write("在本機終端執行以下指令即可下載：")
termlit.write(cmd)

# Or host a temporary HTTP download link
http_links = termlit.download_cmd(
    "report.pdf",
    source_dir="upload_files",
    type="http",
)
termlit.write("也可以使用瀏覽器開啟：")
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
   會產生像 `scp -P 2222 admin@<host>:/abs/path/report.pdf ./` 的字串。把這段
   指令回傳給使用者，請他們複製到本機終端即可。必要時可以透過環境變數
   `TERMLIT_DOWNLOAD_HOST`, `TERMLIT_DOWNLOAD_PORT`, `TERMLIT_DOWNLOAD_USER`
   來調整 host/port/user，或在呼叫時覆寫 `host=`, `port=`, `username=`,
   `destination=`。
2. **HTTP 下載** – 傳入 `type="http"`，例如
   `termlit.download_cmd("report.pdf", source_dir="upload_files", type="http")`，
   會在指定資料夾啟動 `http.server`（預設 port `8765` 可用
   `TERMLIT_HTTP_PORT` 覆寫），並回傳 `http://<host>:8765/report.pdf` 這類
   URL。使用者只要在瀏覽器輸入/點擊即可下載；伺服器端的 access log 也會被
   自動抑制，避免干擾 SSH 介面。

> HTTP 模式要求所有檔案在同一個資料夾，可將檔案集中到 `upload_files/`
> 後再生成連結。下載完記得通知使用者關閉臨時 HTTP server（重新啟動 app
> 或自訂指令）以維持安全。

## Repository layout
- `termlit/session.py` – public helper implementations.
- `termlit/runtime.py` – SSH server + script runner.
- `termlit/cli.py` – command line interface (`termlit run`).
- `termlit/ssh_server_plain.py`, `termlit/telnet_server.py` – original demo servers (optional utilities; they call an external FastAPI backend that you must run yourself).
- `termlit/start_services.py` – helper script that starts the Telnet/SSH demos and forwards the `--fastapi-url` you provide.

Happy terminal building!

## 開發者程式概覽
- `termlit/__init__.py`：集中 re-export Termlit 公開 API（welcome、input、upload_file...），也在匯入時載入版本資訊與 thread-local session 綁定。
- `termlit/session.py`：Session 層主程式，實作所有對外 helper（UI、HTTP、上傳/下載等），並維護 `_current_session`、檔案複製、HTTP 下載服務等細節。
- `termlit/runtime.py`：啟動/管理 SSH 伺服器與 ScriptRunner，並提供 `serve_script_with_reloader` 的 watchdog 流程；同時處理 Paramiko server interface 與 stdout 轉導。
- `termlit/cli.py`：`termlit` 指令的進入點，解析 `termlit run` 旗標、管理授權設定並呼叫 runtime。
- `example_app.py`：內建範例，展示如何建立 Termlit 流程、上傳檔案以及和 HTTP API 互動。
- `termlit/ssh_server_plain.py` / `termlit/telnet_server.py`：較早期的互動式 demo 伺服器，提供自建命令列介面並透過外部 FastAPI 後端提供應答。
- `termlit/start_services.py`：方便一次啟動 telnet/ssh demo 並將 `--fastapi-url` 轉給兩端。
- `tests/`：單元/整合測試樣本；新增功能時請補上覆蓋相關 helper 或 runtime 的測試。
- `upload_files/`：預設的伺服器端上傳輸出資料夾（可透過 `TERMLIT_UPLOAD_DIR` 覆寫），便於從本機取得 Termlit Session 中產生的檔案。
