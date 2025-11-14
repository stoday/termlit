#!/usr/bin/env python3
"""
SSH 服務器 - Rich 美化版本
使用 Rich 但避免複雜排版，適用於 SSH 終端
"""

import os
import sys
import socket
import threading
import requests
import paramiko
import time
from datetime import datetime
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich import print as rprint
from io import StringIO

# 添加當前目錄到 Python 路徑
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

class SSHShell(paramiko.ServerInterface):
    """SSH Shell 處理器 - 純文字版"""
    
    def __init__(self, username, client_address, fastapi_url="http://localhost:8000"):
        self.username = username
        self.client_address = client_address
        self.fastapi_url = fastapi_url
        self.current_path = "C:\\"
        self.channel = None
    
    def check_auth_password(self, username, password):
        """密碼認證"""
        users = {
            "admin": "password123",
            "user": "userpass", 
            "guest": "guest",
            "demo": "demo123"
        }
        
        if username in users and users[username] == password:
            self.username = username
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED
    
    def check_channel_request(self, kind, chanid):
        """檢查通道請求"""
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
    
    def check_channel_shell_request(self, channel):
        """檢查 shell 請求"""
        self.channel = channel
        return True
    
    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        """檢查 PTY 請求"""
        return True
    
    def send_prompt(self):
        """發送命令提示符"""
        if not self.channel:
            return
        prompt = self.username + "@fileserver:" + self.current_path + "$ "
        try:
            self.channel.send(prompt.encode('ascii', errors='ignore'))
        except:
            pass
    
    def safe_send(self, message):
        """安全地發送訊息 - 清理所有隱藏字符"""
        if self.channel and not self.channel.closed:
            try:
                import re
                # 移除所有可能的問題字符，只保留基本字符
                clean_message = re.sub(r'[^\x20-\x7E\n\r\t]', '', str(message))
                
                # 確保結尾有換行
                if not clean_message.endswith('\n'):
                    clean_message += '\n'
                
                self.channel.send(clean_message.encode('ascii', errors='ignore'))
            except Exception as e:
                print(f"發送訊息失敗: {e}")
    
    def run_shell(self):
        """運行 shell 會話"""
        if not self.channel:
            print("錯誤: channel 未設置")
            return
            
        try:
            self.show_welcome()
            
            buffer = ""
            while True:
                try:
                    data = self.channel.recv(1024)
                    if not data:
                        break
                    
                    text = data.decode('utf-8')
                    
                    for char in text:
                        if char == '\r' or char == '\n':
                            if buffer.strip():
                                command = buffer.strip()
                                if command.lower() in ['quit', 'exit']:
                                    self.show_goodbye()
                                    return
                                self.process_command(command)
                            buffer = ""
                            self.send_prompt()
                        elif char == '\x03':  # Ctrl+C
                            self.channel.send("\n^C\n".encode('utf-8'))
                            buffer = ""
                            self.send_prompt()
                        elif char == '\x7f' or char == '\x08':  # Backspace
                            if buffer:
                                buffer = buffer[:-1]
                                self.channel.send("\x08 \x08".encode('utf-8'))
                        elif char.isprintable():
                            buffer += char
                            self.channel.send(char.encode('utf-8'))
                
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    print(f"Shell 處理錯誤: {e}")
                    break
        
        except Exception as e:
            print(f"SSH Shell 會話錯誤: {e}")
        finally:
            try:
                if self.channel:
                    self.channel.close()
            except:
                pass
    
    def show_welcome(self):
        """顯示歡迎畫面 - 使用 Rich 美化"""
        if not self.channel:
            return
        
        try:
            # 使用 rich 創建美化的歡迎訊息
            console = Console(file=StringIO(), width=60, force_terminal=True)
            
            # 創建歡迎面板
            welcome_content = Text()
            welcome_content.append("使用者: ", style="cyan")
            welcome_content.append(str(self.username), style="bright_green")
            welcome_content.append("\n來源: ", style="cyan")
            welcome_content.append(str(self.client_address[0]), style="yellow")
            welcome_content.append("\n時間: ", style="cyan")
            welcome_content.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), style="magenta")
            welcome_content.append("\n\n輸入 ", style="white")
            welcome_content.append("'help'", style="bright_blue")
            welcome_content.append(" 查看可用指令", style="white")
            
            panel = Panel(
                welcome_content,
                title="[bold blue]SSH 檔案目錄伺服器[/bold blue]",
                border_style="green",
                padding=(1, 2)
            )
            
            console.print(panel)
            
            # 獲取 rich 輸出並發送
            rich_output = console.file.getvalue()
            
            # 轉換為適合 SSH 的格式
            ssh_output = rich_output.replace('\n', '\r\n') + '\r\n'
            
            self.channel.send(ssh_output.encode('utf-8'))
            
        except Exception as e:
            print(f"Rich welcome message error: {e}")
            # 如果 Rich 失敗，回退到簡單文字
            fallback_text = (
                "=== SSH 檔案目錄伺服器 ===\r\n"
                "使用者: " + str(self.username) + "\r\n"
                "來源: " + str(self.client_address[0]) + "\r\n"
                "時間: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\r\n"
                "輸入 'help' 查看可用指令\r\n"
                "============================\r\n"
            )
            self.channel.send(fallback_text.encode('utf-8'))
        
        self.send_prompt()
    
    def process_command(self, command: str):
        """處理命令"""
        parts = command.split()
        if not parts:
            return
        
        cmd = parts[0].lower()
        
        try:
            if cmd == 'help':
                self.show_help()
            elif cmd in ['ls', 'dir']:
                path = parts[1] if len(parts) > 1 else self.current_path
                self.list_directory(path)
            elif cmd == 'cd':
                path = parts[1] if len(parts) > 1 else "."
                self.change_directory(path)
            elif cmd == 'pwd':
                self.show_current_path()
            elif cmd == 'whoami':
                self.show_user_info()
            elif cmd == 'status':
                self.show_status()
            elif cmd == 'drives':
                self.show_drives()
            elif cmd == 'info':
                path = parts[1] if len(parts) > 1 else self.current_path
                self.show_file_info(path)
            elif cmd == 'clear':
                self.clear_screen()
            elif cmd in ['quit', 'exit']:
                self.show_goodbye()
                return
            else:
                error_text = f"未知命令: {cmd}\r\n輸入 help 查看可用命令\r\n"
                self.channel.send(error_text.encode('utf-8'))
                
        except Exception as e:
            error_text = f"命令執行錯誤: {str(e)}\r\n"
            self.channel.send(error_text.encode('utf-8'))
    
    def show_help(self):
        """顯示幫助 - 使用 Rich 美化"""
        try:
            help_text = (
                "\r\n=== 可用指令 ===\r\n"
                "help              - 顯示此幫助\r\n"
                "ls [路徑]         - 列出目錄 (例: ls C:\\Users)\r\n"
                "cd <路徑>         - 切換目錄 (例: cd C:\\)\r\n"
                "pwd               - 顯示當前路徑\r\n"
                "whoami            - 顯示當前用戶\r\n"
                "status            - 顯示伺服器狀態\r\n"
                "drives            - 顯示磁碟機 (Windows)\r\n"
                "info <路徑>       - 顯示檔案資訊 (例: info setup.py)\r\n"
                "clear             - 清除螢幕\r\n"
                "quit/exit         - 斷開連接\r\n"
                "=========================\r\n"
                "\r\n"
                "可用帳號:\r\n"
                "admin/password123, user/userpass, guest/guest, demo/demo123\r\n"
                "\r\n"
            )
            self.channel.send(help_text.encode('utf-8'))
            
        except Exception as e:
            print(f"Help message error: {e}")
            # 回退版本
            fallback_text = "Help: ls, cd, pwd, whoami, status, drives, info, clear, quit\r\n"
            self.channel.send(fallback_text.encode('utf-8'))
    
    def list_directory(self, path: str):
        """列出目錄"""
        try:
            response = requests.get(
                f"{self.fastapi_url}/list-directory",
                params={"path": path},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    # 構建完整的目錄列表
                    output_text = f"\r\n目錄: {data['path']}\r\n"
                    output_text += "=" * 50 + "\r\n"
                    
                    # 分類項目
                    dirs = []
                    files = []
                    
                    for item in data['items']:
                        if item['type'] == 'directory':
                            dirs.append(item)
                        else:
                            files.append(item)
                    
                    # 先顯示目錄
                    for item in sorted(dirs, key=lambda x: x['name'].lower()):
                        output_text += f"[DIR]  {item['name']}/\r\n"
                    
                    # 再顯示檔案
                    for item in sorted(files, key=lambda x: x['name'].lower()):
                        size = item.get('size', 0)
                        if size > 1024*1024:
                            size_str = f"{size/(1024*1024):.1f}MB"
                        elif size > 1024:
                            size_str = f"{size/1024:.1f}KB"
                        else:
                            size_str = f"{size}B"
                        
                        output_text += f"[FILE] {item['name']} ({size_str})\r\n"
                    
                    output_text += f"\r\n總計: {len(data['items'])} 個項目 ({len(dirs)} 目錄, {len(files)} 檔案)\r\n"
                    
                    self.channel.send(output_text.encode('utf-8'))
                else:
                    error_text = f"錯誤: {data.get('error', '未知錯誤')}\r\n"
                    self.channel.send(error_text.encode('utf-8'))
                    
            else:
                error_text = f"HTTP 錯誤: {response.status_code}\r\n"
                self.channel.send(error_text.encode('utf-8'))
                
        except requests.RequestException as e:
            error_text = f"連接失敗: {e}\r\n"
            self.channel.send(error_text.encode('utf-8'))
        except Exception as e:
            error_text = f"錯誤: {e}\r\n"
            self.channel.send(error_text.encode('utf-8'))
    
    def change_directory(self, path: str):
        """切換目錄"""
        try:
            response = requests.get(
                f"{self.fastapi_url}/list-directory",
                params={"path": path},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    self.current_path = data['path']
                    success_text = f"已切換到: {self.current_path}\r\n"
                    self.channel.send(success_text.encode('utf-8'))
                else:
                    error_text = f"無法切換到 {path}: {data.get('error', '未知錯誤')}\r\n"
                    self.channel.send(error_text.encode('utf-8'))
            else:
                error_text = f"目錄不存在: {path}\r\n"
                self.channel.send(error_text.encode('utf-8'))
                
        except Exception as e:
            error_text = f"切換目錄失敗: {e}\r\n"
            self.channel.send(error_text.encode('utf-8'))
    
    def show_current_path(self):
        """顯示當前路徑"""
        path_text = f"當前路徑: {self.current_path}\r\n"
        self.channel.send(path_text.encode('utf-8'))
    
    def show_user_info(self):
        """顯示用戶資訊"""
        user_text = f"當前用戶: {self.username}\r\n"
        self.channel.send(user_text.encode('utf-8'))
    
    def show_status(self):
        """顯示狀態"""
        try:
            response = requests.get(f"{self.fastapi_url}/", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                status_text = (
                    f"\r\n伺服器狀態\r\n"
                    f"=============================\r\n"
                    f"服務狀態: {data.get('status', '運行中')}\r\n"
                    f"當前用戶: {self.username}\r\n"
                    f"當前路徑: {self.current_path}\r\n"
                    f"客戶端IP: {self.client_address[0]}\r\n"
                    f"當前時間: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\r\n"
                    f"API狀態: 正常\r\n"
                    f"=============================\r\n"
                )
                
                self.channel.send(status_text.encode('utf-8'))
            else:
                error_text = "無法取得伺服器狀態\r\n"
                self.channel.send(error_text.encode('utf-8'))
                
        except Exception as e:
            error_text = f"取得狀態失敗: {e}\r\n"
            self.channel.send(error_text.encode('utf-8'))
    
    def show_drives(self):
        """顯示磁碟機"""
        try:
            response = requests.get(f"{self.fastapi_url}/get-drives", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    drives_text = "\r\n可用磁碟機:\r\n"
                    drives_text += "=" * 30 + "\r\n"
                    
                    for drive in data['drives']:
                        if isinstance(drive, dict):
                            drives_text += f"{drive['drive']}:\\ ({drive.get('type', 'Unknown')})\r\n"
                        else:
                            drives_text += f"{drive}\r\n"
                    
                    drives_text += "=" * 30 + "\r\n"
                    self.channel.send(drives_text.encode('utf-8'))
                else:
                    error_text = "無法取得磁碟機資訊\r\n"
                    self.channel.send(error_text.encode('utf-8'))
            else:
                error_text = "無法取得磁碟機資訊\r\n"
                self.channel.send(error_text.encode('utf-8'))
                
        except Exception as e:
            error_text = f"取得磁碟機失敗: {e}\r\n"
            self.channel.send(error_text.encode('utf-8'))
    
    def show_file_info(self, path: str):
        """顯示檔案資訊"""
        try:
            response = requests.get(
                f"{self.fastapi_url}/get-file-info",
                params={"path": path},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    info_text = f"\r\n檔案資訊: {data['name']}\r\n"
                    info_text += "=============================\r\n"
                    info_text += f"路徑: {data['path']}\r\n"
                    info_text += f"類型: {data['type']}\r\n"
                    info_text += f"大小: {data.get('size_human', 'N/A')}\r\n"
                    info_text += f"修改時間: {data['modified']}\r\n"
                    info_text += f"建立時間: {data['created']}\r\n"
                    
                    if data.get('extension'):
                        info_text += f"副檔名: {data['extension']}\r\n"
                    
                    info_text += "=============================\r\n"
                    
                    self.channel.send(info_text.encode('utf-8'))
                else:
                    error_text = f"檔案不存在: {path}\r\n"
                    self.channel.send(error_text.encode('utf-8'))
            else:
                error_text = f"檔案不存在: {path}\r\n"
                self.channel.send(error_text.encode('utf-8'))
                
        except Exception as e:
            error_text = f"取得檔案資訊失敗: {e}\r\n"
            self.channel.send(error_text.encode('utf-8'))
    
    def clear_screen(self):
        """清屏"""
        # 發送 ANSI 清屏序列
        self.channel.send(b'\x1b[2J\x1b[H')
    
    def show_goodbye(self):
        """顯示再見訊息"""
        goodbye_text = (
            "\r\n=============================\r\n"
            f"再見, {self.username}！\r\n"
            "感謝使用 SSH 檔案目錄伺服器\r\n"
            "連接即將關閉...\r\n"
            "=============================\r\n\r\n"
        )
        
        self.channel.send(goodbye_text.encode('utf-8'))
        time.sleep(1)
        self.channel.close()

class SSHServer:
    """SSH 服務器"""
    
    def __init__(self, host="127.0.0.1", port=2222, fastapi_url="http://localhost:8000"):
        self.host = host
        self.port = port
        self.fastapi_url = fastapi_url
        self.server_key = None
        self.key_file = "ssh_host_key.pem"  # 金鑰檔案路徑
        self.load_or_generate_server_key()
    
    def load_or_generate_server_key(self):
        """載入或生成服務器金鑰"""
        try:
            # 嘗試載入現有的金鑰
            if os.path.exists(self.key_file):
                print(f"載入現有 SSH 金鑰: {self.key_file}")
                self.server_key = paramiko.RSAKey.from_private_key_file(self.key_file)
                print("SSH 服務器金鑰載入成功")
            else:
                # 生成新金鑰並儲存
                print(f"生成新的 SSH 金鑰: {self.key_file}")
                self.server_key = paramiko.RSAKey.generate(2048)
                self.server_key.write_private_key_file(self.key_file)
                print("SSH 服務器金鑰已生成並儲存")
                
        except Exception as e:
            print(f"處理 SSH 金鑰失敗: {e}")
            # 如果載入失敗，嘗試生成新的
            try:
                print("嘗試生成新金鑰...")
                self.server_key = paramiko.RSAKey.generate(2048)
                self.server_key.write_private_key_file(self.key_file)
                print("新 SSH 金鑰生成成功")
            except Exception as e2:
                print(f"生成 SSH 金鑰失敗: {e2}")
                sys.exit(1)
    
    def handle_client(self, client_socket, client_address):
        """處理客戶端連接"""
        print(f"SSH 連接來自: {client_address}")
        transport = None
        
        try:
            transport = paramiko.Transport(client_socket)
            transport.add_server_key(self.server_key)
            
            # 創建 SSH shell 處理器
            ssh_shell = SSHShell("unknown", client_address, self.fastapi_url)
            
            # 啟動服務器模式，直接傳遞 server 參數
            transport.start_server(server=ssh_shell)
            
            # 等待客戶端認證
            channel = transport.accept(timeout=60)
            if channel is None:
                print(f"SSH 認證失敗: {client_address}")
                return
            
            print(f"SSH 認證成功: {client_address}, 用戶: {ssh_shell.username}")
            
            # 設置 channel 到 shell 處理器
            ssh_shell.channel = channel
            
            # 運行 shell 會話
            ssh_shell.run_shell()
            
        except Exception as e:
            print(f"SSH 連接處理錯誤 {client_address}: {e}")
        finally:
            try:
                if transport:
                    transport.close()
                if client_socket:
                    client_socket.close()
            except Exception as e:
                print(f"關閉連接時發生錯誤: {e}")
        
        print(f"SSH 會話結束: {client_address}")
    
    def start(self):
        """啟動 SSH 服務器"""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            
            print(f"SSH 服務器啟動於 {self.host}:{self.port}")
            print(f"FastAPI 後端: {self.fastapi_url}")
            print("等待客戶端連接...")
            
            while True:
                try:
                    client_socket, client_address = server_socket.accept()
                    # 為每個客戶端創建新線程
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except KeyboardInterrupt:
                    print("\n正在關閉 SSH 服務器...")
                    break
                except Exception as e:
                    print(f"SSH 服務器錯誤: {e}")
                    
        except Exception as e:
            print(f"SSH 服務器啟動失敗: {e}")
        finally:
            try:
                server_socket.close()
            except:
                pass

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SSH 檔案目錄服務器")
    parser.add_argument("--host", default="127.0.0.1", help="服務器地址")
    parser.add_argument("--port", type=int, default=2222, help="SSH 端口")
    parser.add_argument("--fastapi-url", default="http://localhost:8000", help="FastAPI 服務器 URL")
    
    args = parser.parse_args()
    
    server = SSHServer(args.host, args.port, args.fastapi_url)
    server.start()