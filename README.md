# termlit
Termlit converts a plain Python script into an interactive SSH experience.  
Write terminal flows with `welcome`, `input`, and `post` helpers, then expose
them over SSH via `termlit run app.py`.

## Features
- SSH server with ready-to-use credentials (or anonymous mode)
- Built-in Rich welcome panels and simple text helpers
- Rich-powered spinners that lock user input while background work is running
- Request/response helpers (`termlit.post`) powered by `requests`
- Session-scoped stdout redirection so `print()` just works

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
3. Serve it over SSH:
   ```bash
   termlit run app.py --host 0.0.0.0 --port 2222
   ```
4. Connect from any SSH client (default credentials `admin/password123`):
   ```bash
   ssh admin@127.0.0.1 -p 2222
   ```

## CLI flags
- `--user name=secret`: add/override login credentials (repeatable).
- `--allow-anonymous`: accept any username/password combo.
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

## Repository layout
- `termlit/session.py` – public helper implementations.
- `termlit/runtime.py` – SSH server + script runner.
- `termlit/cli.py` – command line interface (`termlit run`).
- `termlit/ssh_server_plain.py`, `termlit/telnet_server.py` – original demo servers (optional utilities).

Happy terminal building!
