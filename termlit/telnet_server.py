"""
美化版 Telnet 服務器 - 提供 Telnet 連接並與 FastAPI 服務器通信
使用 rich 套件美化介面
"""
import socket
import threading
import json
import requests
import time
from datetime import datetime
from typing import Optional
from io import StringIO

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.text import Text
    from rich.columns import Columns
    from rich import box
    from rich.align import Align
except ImportError:
    print("需要安裝 rich 套件: pip install rich")
    # 如果沒有 rich，使用基本版本
    Console = None

class TelnetServer:
    """美化版 Telnet 服務器類"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 2323, fastapi_url: str = "http://127.0.0.1:8000"):
        self.host = host
        self.port = port
        self.fastapi_url = fastapi_url
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        
        # 檢查是否有 rich 支援
        self.rich_enabled = Console is not None
        
    def start(self):
        """啟動 Telnet 服務器"""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"Telnet 服務器啟動於 {self.host}:{self.port}")
            print(f"連接 FastAPI 服務器於 {self.fastapi_url}")
            print("等待客戶端連接...")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    print(f"新連接來自: {address}")
                    
                    # 為每個客戶端創建一個新線程
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error as e:
                    if self.running:
                        print(f"接受連接時發生錯誤: {e}")
                        
        except Exception as e:
            print(f"啟動服務器時發生錯誤: {e}")
        finally:
            self.cleanup()
    
    def stop(self):
        """停止 Telnet 服務器"""
        print("正在停止 Telnet 服務器...")
        self.running = False
        if self.server_socket:
            self.server_socket.close()
    
    def cleanup(self):
        """清理資源"""
        if self.server_socket:
            self.server_socket.close()
        print("Telnet 服務器已停止")
    
    def handle_client(self, client_socket: socket.socket, address):
        """處理客戶端連接 - 美化版"""
        console_buffer = StringIO()
        console = None
        
        if self.rich_enabled:
            console = Console(
                file=console_buffer, 
                force_terminal=True, 
                width=80,
                color_system="truecolor"
            )
        
        def send_rich_message(message_text: str, use_rich: bool = True):
            """發送訊息，支援 Rich 格式化"""
            if self.rich_enabled and use_rich and console:
                console.print(message_text)
                content = console_buffer.getvalue()
                if content:
                    client_socket.send(content.encode('utf-8'))
                    console_buffer.seek(0)
                    console_buffer.truncate(0)
            else:
                client_socket.send(message_text.encode('utf-8'))
        
        try:
            # 發送美化的登入畫面
            if self.rich_enabled and console:
                login_panel = Panel(
                    Text.assemble(
                        ("🔐 ", ""),
                        ("Telnet 檔案目錄服務", "bold cyan"),
                        ("\n\n"),
                        ("連接時間: ", "bold"),
                        (f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "green"),
                        ("\n"),
                        ("來源 IP: ", "bold"),
                        (f"{address[0]}", "yellow"),
                        ("\n\n"),
                        ("請先登入系統", "bold red"),
                    ),
                    box=box.DOUBLE_EDGE,
                    border_style="bright_blue",
                    title="[bold white]📡 ClockMate Telnet Server 📡[/bold white]",
                    title_align="center"
                )
                console.print(login_panel)
                console.print("\n[bold cyan]Username:[/bold cyan] ", end="")
                send_rich_message("", False)  # 發送緩衝區內容
            else:
                # 基本版登入訊息
                login_msg = (
                    "\n╭─────────────────────────────────────╮\n"
                    "│     📡 Telnet 檔案目錄服務         │\n"
                    f"│     時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<19}│\n"
                    f"│     來源: {address[0]:<19}│\n"
                    "╰─────────────────────────────────────╯\n"
                    "請先登入系統\n"
                    "Username: "
                )
                send_rich_message(login_msg, False)
            
            # 處理登入認證
            authenticated_user = self.authenticate_user(client_socket, address, console, send_rich_message)
            if not authenticated_user:
                send_rich_message("\n❌ 認證失敗，連接已關閉。\n", False)
                return
            
            # 發送美化的歡迎訊息
            if self.rich_enabled and console:
                welcome_panel = Panel(
                    Text.assemble(
                        ("🎉 ", ""),
                        ("歡迎, ", "bold"),
                        (f"{authenticated_user}", "bold green"),
                        ("!", "bold"),
                        ("\n\n"),
                        ("💡 輸入 ", ""),
                        ("help", "bold yellow"),
                        (" 查看可用命令", ""),
                        ("\n"),
                        ("💡 輸入 ", ""),
                        ("quit", "bold red"),
                        (" 或 ", ""),
                        ("exit", "bold red"),
                        (" 退出", ""),
                    ),
                    box=box.ROUNDED,
                    border_style="green",
                    title="✅ 登入成功",
                    title_align="center"
                )
                console.print(welcome_panel)
                send_rich_message("", False)
            else:
                welcome_msg = (
                    f"\n✅ 歡迎, {authenticated_user}!\n"
                    "輸入 'help' 查看可用命令\n"
                    "輸入 'quit' 或 'exit' 退出\n"
                )
                send_rich_message(welcome_msg, False)
            
            current_path = "."  # 當前路徑
            
            # 發送提示符
            def send_prompt():
                if self.rich_enabled and console:
                    prompt_text = Text()
                    prompt_text.append(f"\n{authenticated_user}", style="bold cyan")
                    prompt_text.append("@", style="white")
                    prompt_text.append("telnet-server", style="bold green")
                    prompt_text.append(":", style="white")
                    prompt_text.append(f"{current_path}", style="bold blue")
                    prompt_text.append("$ ", style="bold white")
                    console.print(prompt_text, end="")
                    send_rich_message("", False)
                else:
                    send_rich_message(f"\n{authenticated_user}@telnet-server:{current_path}$ ", False)
            
            send_prompt()
            
            while True:
                try:
                    # 接收命令
                    data = client_socket.recv(1024).decode('utf-8').strip()
                    if not data:
                        break
                    
                    print(f"收到來自 {address} ({authenticated_user}) 的命令: {data}")
                    
                    # 處理命令
                    response = self.process_command(data, current_path, authenticated_user, console)
                    
                    # 如果命令改變了當前路徑，更新它
                    if data.startswith('cd '):
                        new_path = data[3:].strip()
                        if new_path and self.is_valid_directory(new_path):
                            current_path = new_path
                    
                    # 發送回應
                    if response:
                        send_rich_message(response, self.rich_enabled)
                    
                    # 如果是退出命令，結束連接
                    if data.lower() in ['quit', 'exit']:
                        break
                    
                    send_prompt()
                        
                except socket.timeout:
                    continue
                except socket.error as e:
                    print(f"客戶端 {address} 連接錯誤: {e}")
                    break
                    
        except Exception as e:
            print(f"處理客戶端 {address} 時發生錯誤: {e}")
        finally:
            client_socket.close()
            print(f"客戶端 {address} 已斷開連接")
    
    def authenticate_user(self, client_socket: socket.socket, address, console=None, send_message_func=None) -> str:
        """處理用戶認證 - 美化版"""
        # 預設用戶清單
        users = {
            "admin": "password123",
            "user": "userpass",
            "guest": "guest",
            "demo": "demo123"
        }
        
        max_attempts = 3
        attempts = 0
        
        while attempts < max_attempts:
            try:
                # 接收用戶名
                username_data = client_socket.recv(1024).decode('utf-8').strip()
                if not username_data:
                    return None
                
                username = username_data.replace('\r', '').replace('\n', '')
                
                # 發送密碼提示
                if self.rich_enabled and console:
                    console.print(f"\n[bold cyan]Password for {username}:[/bold cyan] ", end="")
                    content = console._file.getvalue()
                    if content:
                        client_socket.send(content.encode('utf-8'))
                        console._file.seek(0)
                        console._file.truncate(0)
                else:
                    client_socket.send(f"\nPassword for {username}: ".encode('utf-8'))
                
                # 接收密碼
                password_data = client_socket.recv(1024).decode('utf-8').strip()
                if not password_data:
                    return None
                
                password = password_data.replace('\r', '').replace('\n', '')
                
                # 驗證用戶名和密碼
                if username in users and users[username] == password:
                    print(f"用戶 {username} 從 {address} 登入成功")
                    return username
                else:
                    attempts += 1
                    remaining = max_attempts - attempts
                    
                    if remaining > 0:
                        if self.rich_enabled and console:
                            error_panel = Panel(
                                f"[red]❌ 登入失敗![/red]\n[yellow]剩餘嘗試次數: {remaining}[/yellow]",
                                border_style="red",
                                title="認證錯誤"
                            )
                            console.print(error_panel)
                            console.print("\n[bold cyan]Username:[/bold cyan] ", end="")
                            content = console._file.getvalue()
                            if content:
                                client_socket.send(content.encode('utf-8'))
                                console._file.seek(0)
                                console._file.truncate(0)
                        else:
                            error_msg = f"\n❌ 登入失敗! 剩餘嘗試次數: {remaining}\nUsername: "
                            client_socket.send(error_msg.encode('utf-8'))
                        
                        print(f"用戶 {username} 從 {address} 登入失敗 (剩餘嘗試次數: {remaining})")
                    else:
                        if self.rich_enabled and console:
                            final_error = Panel(
                                "[red]❌ 超過登入嘗試次數限制![/red]\n[yellow]連接將被關閉[/yellow]",
                                border_style="red",
                                title="認證失敗"
                            )
                            console.print(final_error)
                            content = console._file.getvalue()
                            if content:
                                client_socket.send(content.encode('utf-8'))
                        else:
                            client_socket.send("\n❌ 超過登入嘗試次數限制!\n".encode('utf-8'))
                        
                        print(f"客戶端 {address} 超過登入嘗試次數限制")
                        
            except Exception as e:
                print(f"認證過程中發生錯誤 {address}: {e}")
                break
        
        return None
    
    def process_command(self, command: str, current_path: str, username: str = "unknown", console=None) -> str:
        """處理用戶命令 - 美化版"""
        original_command = command.strip()
        command = command.strip().lower()
        
        if command == 'help':
            return self.get_help_message(console)
        elif command in ['quit', 'exit']:
            if self.rich_enabled and console:
                goodbye_panel = Panel(
                    f"[green]再見, [bold cyan]{username}[/bold cyan]！[/green]\n[yellow]連接即將關閉...[/yellow]",
                    border_style="green",
                    title="再見"
                )
                console.print(goodbye_panel)
                return console._file.getvalue()
            else:
                return f"再見, {username}！連接即將關閉。\n"
        elif command == 'pwd':
            if self.rich_enabled and console:
                pwd_panel = Panel(
                    f"[cyan]當前路徑:[/cyan] [bold green]{current_path}[/bold green]",
                    border_style="cyan",
                    title="當前位置"
                )
                console.print(pwd_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"當前路徑: {current_path}\n> "
        elif command == 'ls' or command == 'dir':
            return self.list_directory(current_path, console)
        elif command.startswith('ls ') or command.startswith('dir '):
            path = original_command.split(' ', 1)[1]
            return self.list_directory(path, console)
        elif command.startswith('cd '):
            path = original_command[3:].strip()
            return self.change_directory(path, current_path, console)
        elif command == 'drives':
            return self.get_drives(console)
        elif command.startswith('info '):
            path = original_command[5:].strip()
            return self.get_file_info(path, console)
        elif command == 'status':
            return self.get_status(username, console)
        elif command == 'whoami':
            if self.rich_enabled and console:
                whoami_panel = Panel(
                    f"[cyan]當前用戶:[/cyan] [bold green]{username}[/bold green]",
                    border_style="cyan",
                    title="用戶信息"
                )
                console.print(whoami_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"當前用戶: {username}\n> "
        else:
            if self.rich_enabled and console:
                unknown_panel = Panel(
                    f"[red]未知命令:[/red] [yellow]{original_command}[/yellow]\n[cyan]輸入 'help' 查看可用命令[/cyan]",
                    border_style="red",
                    title="命令錯誤"
                )
                console.print(unknown_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"未知命令: {original_command}\n輸入 'help' 查看可用命令\n> "
    
    def get_help_message(self, console=None) -> str:
        """返回幫助信息 - 美化版"""
        if self.rich_enabled and console:
            console.print("[bold cyan]可用命令:[/bold cyan]")
            console.print("=" * 40)
            
            commands = [
                ("help", "顯示此幫助信息"),
                ("ls, dir", "列出當前目錄內容"),
                ("ls <path>", "列出指定目錄內容"),
                ("cd <path>", "切換到指定目錄"),
                ("pwd", "顯示當前路徑"),
                ("drives", "顯示可用磁碟機（Windows）"),
                ("info <path>", "顯示檔案/目錄詳細資訊"),
                ("status", "顯示服務器狀態"),
                ("whoami", "顯示當前登入用戶"),
                ("quit, exit", "退出連接")
            ]
            
            for cmd, desc in commands:
                console.print(f"[green]{cmd:15}[/green] - {desc}")
            
            console.print(f"\n[bold yellow]認證帳號:[/bold yellow]")
            console.print("admin/password123, user/userpass, guest/guest, demo/demo123")
            
            console.print(f"\n[bold blue]範例:[/bold blue]")
            console.print("ls C:\\Users")
            console.print("cd C:\\")
            console.print("info setup.py")
            
            console.print("\n[bold yellow]>[/bold yellow] ", end="")
            return console._file.getvalue()
        else:
            help_text = """
=== 可用命令 ===
help        - 顯示此幫助信息
ls, dir     - 列出當前目錄內容
ls <path>   - 列出指定目錄內容
cd <path>   - 切換到指定目錄
pwd         - 顯示當前路徑
drives      - 顯示可用磁碟機（Windows）
info <path> - 顯示檔案/目錄詳細資訊
status      - 顯示服務器狀態
whoami      - 顯示當前登入用戶
quit, exit  - 退出連接

認證資訊：
- 預設帳號：admin/password123, user/userpass, guest/guest, demo/demo123
- 最多3次登入嘗試
- 登入失敗將斷開連接

範例:
  ls C:\\Users
  cd C:\\
  info setup.py
  drives

> """
            return help_text
    
    def list_directory(self, path: str, console=None) -> str:
        """列出目錄內容 - 簡化版"""
        try:
            response = requests.get(
                f"{self.fastapi_url}/list-directory",
                params={"path": path},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    if self.rich_enabled and console:
                        console.print(f"[bold cyan]目錄:[/bold cyan] {data['path']}")
                        console.print("=" * 50)
                        
                        # 分類並排序項目
                        dirs = sorted([item for item in data['items'] if item['type'] == 'directory'], 
                                    key=lambda x: x['name'].lower())
                        files = sorted([item for item in data['items'] if item['type'] == 'file'], 
                                     key=lambda x: x['name'].lower())
                        
                        # 顯示目錄
                        for item in dirs:
                            console.print(f"[blue]DIR[/blue]  {item['name']}")
                        
                        # 顯示檔案
                        for item in files:
                            size_bytes = item.get('size', 0)
                            if size_bytes < 1024:
                                size_str = f"{size_bytes} B"
                            elif size_bytes < 1024 * 1024:
                                size_str = f"{size_bytes / 1024:.1f} KB"
                            else:
                                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                            
                            console.print(f"[green]FILE[/green] {item['name']} [yellow]({size_str})[/yellow]")
                        
                        console.print(f"\n[bold]總計:[/bold] [cyan]{data['total_items']}[/cyan] 個項目")
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        result = f"\n目錄: {data['path']}\n"
                        result += "=" * 50 + "\n"
                        
                        for item in data['items']:
                            item_type = "[DIR]" if item['type'] == 'directory' else "[FILE]"
                            size = f"({item.get('size', 0)} bytes)" if item['type'] == 'file' else ""
                            result += f"{item_type:8} {item['name']:30} {size}\n"
                        
                        result += f"\n總計: {data['total_items']} 個項目\n> "
                        return result
                else:
                    if self.rich_enabled and console:
                        console.print(f"[red]錯誤:[/red] {data.get('error', '未知錯誤')}")
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        return f"錯誤: {data.get('error', '未知錯誤')}\n> "
            else:
                if self.rich_enabled and console:
                    console.print(f"[red]HTTP 錯誤:[/red] {response.status_code}")
                    console.print("\n[bold yellow]>[/bold yellow] ", end="")
                    return console._file.getvalue()
                else:
                    return f"HTTP 錯誤: {response.status_code}\n> "
                
        except requests.RequestException as e:
            if self.rich_enabled and console:
                console.print(f"[red]連接 FastAPI 服務器失敗:[/red] {str(e)}")
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"連接 FastAPI 服務器失敗: {e}\n> "
        except Exception as e:
            if self.rich_enabled and console:
                console.print(f"[red]處理請求時發生錯誤:[/red] {str(e)}")
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"處理請求時發生錯誤: {e}\n> "
    
    def change_directory(self, path: str, current_path: str, console=None) -> str:
        """切換目錄 - 美化版"""
        try:
            # 檢查目標路徑是否存在
            response = requests.get(
                f"{self.fastapi_url}/list-directory",
                params={"path": path},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    if self.rich_enabled and console:
                        success_panel = Panel(
                            f"[green]✓ 已成功切換到:[/green]\n[bold cyan]{data['path']}[/bold cyan]",
                            border_style="green",
                            title="目錄切換"
                        )
                        console.print(success_panel)
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        return f"已切換到: {data['path']}\n> "
                else:
                    if self.rich_enabled and console:
                        error_panel = Panel(
                            f"[red]✗ 無法切換到:[/red] [yellow]{path}[/yellow]\n[red]錯誤:[/red] {data.get('error', '未知錯誤')}",
                            border_style="red",
                            title="切換失敗"
                        )
                        console.print(error_panel)
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        return f"無法切換到 {path}: {data.get('error', '未知錯誤')}\n> "
            else:
                if self.rich_enabled and console:
                    path_error_panel = Panel(
                        f"[red]✗ 路徑不存在或無權限存取:[/red]\n[yellow]{path}[/yellow]",
                        border_style="red",
                        title="訪問錯誤"
                    )
                    console.print(path_error_panel)
                    console.print("\n[bold yellow]>[/bold yellow] ", end="")
                    return console._file.getvalue()
                else:
                    return f"路徑不存在或無權限存取: {path}\n> "
                
        except requests.RequestException as e:
            if self.rich_enabled and console:
                conn_error_panel = Panel(
                    f"[red]連接 FastAPI 服務器失敗:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="服務器錯誤"
                )
                console.print(conn_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"連接 FastAPI 服務器失敗: {e}\n> "
        except Exception as e:
            if self.rich_enabled and console:
                general_error_panel = Panel(
                    f"[red]切換目錄時發生錯誤:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="未知錯誤"
                )
                console.print(general_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"切換目錄時發生錯誤: {e}\n> "
    
    def get_file_info(self, path: str, console=None) -> str:
        """獲取檔案資訊 - 美化版"""
        try:
            response = requests.get(
                f"{self.fastapi_url}/get-file-info",
                params={"path": path},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    info = data
                    
                    if self.rich_enabled and console:
                        from rich.table import Table
                        
                        # 創建檔案資訊表格
                        info_table = Table(
                            title=f"📄 檔案資訊: {info['name']}",
                            show_header=True,
                            header_style="bold cyan",
                            border_style="blue"
                        )
                        info_table.add_column("屬性", style="bold green", width=12)
                        info_table.add_column("值", style="white", width=40)
                        
                        # 添加檔案資訊
                        info_table.add_row("路徑", info['path'])
                        info_table.add_row("類型", "📁 目錄" if info['type'] == 'directory' else "📄 檔案")
                        info_table.add_row("大小", info.get('size_human', 'N/A'))
                        info_table.add_row("修改時間", info['modified'])
                        info_table.add_row("建立時間", info['created'])
                        
                        if info.get('extension'):
                            info_table.add_row("副檔名", info['extension'])
                        
                        console.print(info_table)
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        result = f"\n檔案資訊: {info['name']}\n"
                        result += "=" * 40 + "\n"
                        result += f"路徑: {info['path']}\n"
                        result += f"類型: {info['type']}\n"
                        result += f"大小: {info.get('size_human', 'N/A')}\n"
                        result += f"修改時間: {info['modified']}\n"
                        result += f"建立時間: {info['created']}\n"
                        if info.get('extension'):
                            result += f"副檔名: {info['extension']}\n"
                        result += "\n> "
                        return result
                else:
                    if self.rich_enabled and console:
                        error_panel = Panel(
                            f"[red]錯誤:[/red] [yellow]{data.get('error', '未知錯誤')}[/yellow]",
                            border_style="red",
                            title="檔案資訊錯誤"
                        )
                        console.print(error_panel)
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        return f"錯誤: {data.get('error', '未知錯誤')}\n> "
            else:
                if self.rich_enabled and console:
                    http_error_panel = Panel(
                        f"[red]HTTP 錯誤:[/red] [yellow]{response.status_code}[/yellow]",
                        border_style="red",
                        title="連接錯誤"
                    )
                    console.print(http_error_panel)
                    console.print("\n[bold yellow]>[/bold yellow] ", end="")
                    return console._file.getvalue()
                else:
                    return f"HTTP 錯誤: {response.status_code}\n> "
                
        except requests.RequestException as e:
            if self.rich_enabled and console:
                conn_error_panel = Panel(
                    f"[red]連接 FastAPI 服務器失敗:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="服務器錯誤"
                )
                console.print(conn_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"連接 FastAPI 服務器失敗: {e}\n> "
        except Exception as e:
            if self.rich_enabled and console:
                general_error_panel = Panel(
                    f"[red]獲取檔案資訊時發生錯誤:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="未知錯誤"
                )
                console.print(general_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"獲取檔案資訊時發生錯誤: {e}\n> "
    
    def get_drives(self, console=None) -> str:
        """獲取磁碟機列表 - 美化版"""
        try:
            response = requests.get(f"{self.fastapi_url}/get-drives", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    if self.rich_enabled and console:
                        from rich.table import Table
                        
                        # 創建磁碟機表格
                        drives_table = Table(
                            title="💾 可用磁碟機",
                            show_header=True,
                            header_style="bold cyan",
                            border_style="blue"
                        )
                        drives_table.add_column("磁碟機", style="bold green", width=8)
                        drives_table.add_column("類型", style="yellow", width=15)
                        drives_table.add_column("路徑", style="white", width=20)
                        
                        for drive in data['drives']:
                            if isinstance(drive, dict):
                                drive_letter = drive['drive']
                                drive_type = drive.get('type', 'Unknown')
                                drive_path = f"{drive_letter}:\\"
                                
                                # 根據磁碟機類型選擇圖示
                                if 'Fixed' in drive_type:
                                    icon = "🖥️"
                                elif 'Removable' in drive_type:
                                    icon = "💾"
                                elif 'CDRom' in drive_type:
                                    icon = "💿"
                                else:
                                    icon = "💽"
                                
                                drives_table.add_row(f"{icon} {drive_letter}:", drive_type, drive_path)
                            else:
                                drives_table.add_row(f"💽 {drive}:", "Unknown", f"{drive}\\")
                        
                        console.print(drives_table)
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        result = "\n可用磁碟機:\n"
                        result += "=" * 30 + "\n"
                        
                        for drive in data['drives']:
                            if isinstance(drive, dict):
                                result += f"{drive['drive']}:\\ ({drive.get('type', 'Unknown')})\n"
                            else:
                                result += f"{drive}\n"
                        
                        result += "\n> "
                        return result
                else:
                    if self.rich_enabled and console:
                        error_panel = Panel(
                            f"[red]錯誤:[/red] [yellow]{data.get('error', '未知錯誤')}[/yellow]",
                            border_style="red",
                            title="磁碟機列表錯誤"
                        )
                        console.print(error_panel)
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        return f"錯誤: {data.get('error', '未知錯誤')}\n> "
            else:
                if self.rich_enabled and console:
                    http_error_panel = Panel(
                        f"[red]HTTP 錯誤:[/red] [yellow]{response.status_code}[/yellow]",
                        border_style="red",
                        title="連接錯誤"
                    )
                    console.print(http_error_panel)
                    console.print("\n[bold yellow]>[/bold yellow] ", end="")
                    return console._file.getvalue()
                else:
                    return f"HTTP 錯誤: {response.status_code}\n> "
                
        except requests.RequestException as e:
            if self.rich_enabled and console:
                conn_error_panel = Panel(
                    f"[red]連接 FastAPI 服務器失敗:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="服務器錯誤"
                )
                console.print(conn_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"連接 FastAPI 服務器失敗: {e}\n> "
        except Exception as e:
            if self.rich_enabled and console:
                general_error_panel = Panel(
                    f"[red]獲取磁碟機列表時發生錯誤:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="未知錯誤"
                )
                console.print(general_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"獲取磁碟機列表時發生錯誤: {e}\n> "
    
    def get_status(self, username: str = "unknown", console=None) -> str:
        """獲取服務器狀態 - 美化版"""
        try:
            response = requests.get(f"{self.fastapi_url}/", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                if self.rich_enabled and console:
                    from rich.table import Table
                    import datetime
                    
                    # 創建狀態表格
                    status_table = Table(
                        title="⚡ 服務器狀態",
                        show_header=True,
                        header_style="bold cyan",
                        border_style="green"
                    )
                    status_table.add_column("服務", style="bold green", width=15)
                    status_table.add_column("狀態", style="white", width=15)
                    status_table.add_column("詳細資訊", style="yellow", width=30)
                    
                    # FastAPI 狀態
                    fastapi_status = data.get('status', 'Unknown')
                    if fastapi_status.lower() == 'ok':
                        status_emoji = "✅"
                        status_color = "[green]運行正常[/green]"
                    else:
                        status_emoji = "❌"
                        status_color = "[red]異常[/red]"
                    
                    status_table.add_row(
                        "🌐 FastAPI",
                        f"{status_emoji} {status_color}",
                        data.get('message', 'N/A')
                    )
                    
                    # Telnet 狀態
                    status_table.add_row(
                        "📡 Telnet",
                        "✅ [green]運行中[/green]",
                        f"{self.host}:{self.port}"
                    )
                    
                    # 用戶資訊
                    status_table.add_row(
                        "👤 用戶",
                        "✅ [green]已登入[/green]",
                        username
                    )
                    
                    # 時間資訊
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    status_table.add_row(
                        "🕒 系統時間",
                        "✅ [green]同步[/green]",
                        current_time
                    )
                    
                    console.print(status_table)
                    
                    # 額外資訊面板
                    if data.get('timestamp'):
                        info_panel = Panel(
                            f"[cyan]FastAPI 時間戳:[/cyan] {data['timestamp']}",
                            border_style="blue",
                            title="額外資訊"
                        )
                        console.print(info_panel)
                    
                    console.print("\n[bold yellow]>[/bold yellow] ", end="")
                    return console._file.getvalue()
                else:
                    result = f"\nFastAPI 服務器狀態: {data.get('status', 'Unknown')}\n"
                    result += f"服務訊息: {data.get('message', 'N/A')}\n"
                    result += f"時間戳: {data.get('timestamp', 'N/A')}\n"
                    result += f"\nTelnet 服務器: 運行中於 {self.host}:{self.port}\n"
                    result += f"當前用戶: {username}\n"
                    result += "\n> "
                    return result
            else:
                if self.rich_enabled and console:
                    error_panel = Panel(
                        f"[red]FastAPI 服務器無回應[/red]\n[yellow]HTTP 狀態碼: {response.status_code}[/yellow]",
                        border_style="red",
                        title="服務器錯誤"
                    )
                    console.print(error_panel)
                    console.print("\n[bold yellow]>[/bold yellow] ", end="")
                    return console._file.getvalue()
                else:
                    return f"FastAPI 服務器無回應 (HTTP {response.status_code})\n> "
                
        except requests.RequestException as e:
            if self.rich_enabled and console:
                conn_error_panel = Panel(
                    f"[red]無法連接到 FastAPI 服務器:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="連接錯誤"
                )
                console.print(conn_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"無法連接到 FastAPI 服務器: {e}\n> "
        except Exception as e:
            if self.rich_enabled and console:
                general_error_panel = Panel(
                    f"[red]獲取狀態時發生錯誤:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="未知錯誤"
                )
                console.print(general_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"獲取狀態時發生錯誤: {e}\n> "
    
    def is_valid_directory(self, path: str) -> bool:
        """檢查路徑是否為有效目錄"""
        try:
            response = requests.get(
                f"{self.fastapi_url}/list-directory",
                params={"path": path},
                timeout=5
            )
            return response.status_code == 200 and response.json().get("success", False)
        except:
            return False

def start_telnet_server(host: str = "127.0.0.1", port: int = 2323, fastapi_url: str = "http://127.0.0.1:8000"):
    """啟動 Telnet 服務器"""
    server = TelnetServer(host, port, fastapi_url)
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n收到中斷信號，正在停止服務器...")
        server.stop()
    except Exception as e:
        print(f"服務器錯誤: {e}")
        server.stop()

if __name__ == "__main__":
    # 等待 FastAPI 服務器啟動
    print("等待 FastAPI 服務器啟動...")
    time.sleep(2)
    start_telnet_server()