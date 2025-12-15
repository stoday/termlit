#!/usr/bin/env python3
"""
SSH Server - Rich Beautified Version
Uses Rich but avoids complex layouts, suitable for SSH terminals
"""

import os
import sys
import socket
import threading
import requests
import paramiko
import time
import subprocess
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Union
from rich.console import Console
from rich.text import Text
from rich.panel import Panel
from rich import print as rprint
from io import StringIO

# Add current directory to Python Path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

REPO_ROOT = Path(parent_dir).resolve()
DEFAULT_UPLOAD_DIR = REPO_ROOT / "upload_files"

class SSHShell(paramiko.ServerInterface):
    """SSH Shell Handler - Plain Text Version"""
    
    def __init__(self, username, client_address, fastapi_url="http://localhost:8000"):
        self.username = username
        self.client_address = client_address
        self.fastapi_url = fastapi_url
        self.current_path = "C:\\"
        self.channel = None
        self.upload_dir = DEFAULT_UPLOAD_DIR
    
    def check_auth_password(self, username, password):
        """Password Authentication"""
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
        """Check channel request"""
        if kind == 'session':
            return paramiko.OPEN_SUCCEEDED
        return paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED
    
    def check_channel_shell_request(self, channel):
        """Check shell request"""
        self.channel = channel
        return True
    
    def check_channel_pty_request(self, channel, term, width, height, pixelwidth, pixelheight, modes):
        """Check PTY request"""
        return True
    
    def send_prompt(self):
        """Send command prompt"""
        if not self.channel:
            return
        prompt = self.username + "@fileserver:" + self.current_path + "$ "
        try:
            self.channel.send(prompt.encode('ascii', errors='ignore'))
        except:
            pass
    
    def safe_send(self, message):
        """Safely send message - Clean up all hidden characters"""
        if self.channel and not self.channel.closed:
            try:
                import re
                # Remove all potential problematic characters, keep only basic ASCII
                clean_message = re.sub(r'[^\x20-\x7E\n\r\t]', '', str(message))
                
                # Ensure it ends with a newline
                if not clean_message.endswith('\n'):
                    clean_message += '\n'
                
                self.channel.send(clean_message.encode('ascii', errors='ignore'))
            except Exception as e:
                print(f"Failed to send message: {e}")
    
    def run_shell(self):
        """Run shell session"""
        if not self.channel:
            print("Error: channel not set")
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
                    print(f"Shell processing error: {e}")
                    break
        
        except Exception as e:
            print(f"SSH Shell session error: {e}")
        finally:
            try:
                if self.channel:
                    self.channel.close()
            except:
                pass
    
    def show_welcome(self):
        """Show welcome screen - Use Rich for beautification"""
        if not self.channel:
            return
        
        try:
            # Use rich to create beautified welcome message
            console = Console(file=StringIO(), width=60, force_terminal=True)
            
            # Create welcome panel
            welcome_content = Text()
            welcome_content.append("User: ", style="cyan")
            welcome_content.append(str(self.username), style="bright_green")
            welcome_content.append("\nSource: ", style="cyan")
            welcome_content.append(str(self.client_address[0]), style="yellow")
            welcome_content.append("\nTime: ", style="cyan")
            welcome_content.append(datetime.now().strftime('%Y-%m-%d %H:%M:%S'), style="magenta")
            welcome_content.append("\n\nType ", style="white")
            welcome_content.append("'help'", style="bright_blue")
            welcome_content.append(" to see available commands", style="white")
            
            panel = Panel(
                welcome_content,
                title="[bold blue]SSH File Directory Server[/bold blue]",
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
            # If Rich fails, fallback to simple text
            fallback_text = (
                "=== SSH File Directory Server ===\r\n"
                "User: " + str(self.username) + "\r\n"
                "Source: " + str(self.client_address[0]) + "\r\n"
                "Time: " + datetime.now().strftime('%Y-%m-%d %H:%M:%S') + "\r\n"
                "Type 'help' to see available commands\r\n"
                "============================\r\n"
            )
            self.channel.send(fallback_text.encode('utf-8'))
        
        self.send_prompt()
    
    def process_command(self, command: str):
        """Process command"""
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
            elif cmd in ['upload', 'upload_file']:
                if len(parts) < 2:
                    self.upload_file("")
                elif len(parts) == 2:
                    self.upload_file(parts[1])
                else:
                    self.upload_file(parts[1:])
            elif cmd == 'clear':
                self.clear_screen()
            elif cmd in ['quit', 'exit']:
                self.show_goodbye()
                return
            else:
                error_text = f"Unknown command: {cmd}\r\nType help to see available commands\r\n"
                self.channel.send(error_text.encode('utf-8'))
                
        except Exception as e:
            error_text = f"Command execution error: {str(e)}\r\n"
            self.channel.send(error_text.encode('utf-8'))
    
    def show_help(self):
        """Show help - Use Rich for beautification"""
        try:
            help_text = (
                "\r\n=== Available Commands ===\r\n"
                "help              - Show this help\r\n"
                "ls [Path]         - List directory (例: ls C:\\Users)\r\n"
                "cd <Path>         - Change directory (例: cd C:\\)\r\n"
                "pwd               - Show current path\r\n"
                "whoami            - Show current user\r\n"
                "status            - Show server status\r\n"
                "drives            - Show available drives (Windows)\r\n"
                "info <Path>       - Show file info (e.g., info setup.py)\r\n"
                "upload_file <檔案...>\r\n"
                "                  - Copy one or more files to upload_files directory\r\n"
                "clear             - Clear screen\r\n"
                "quit/exit         - Disconnect\r\n"
                "=========================\r\n"
                "\r\n"
                "Available Accounts:\r\n"
                "admin/password123, user/userpass, guest/guest, demo/demo123\r\n"
                "\r\n"
            )
            self.channel.send(help_text.encode('utf-8'))
            
        except Exception as e:
            print(f"Help message error: {e}")
            # Fallback version
            fallback_text = "Help: ls, cd, pwd, whoami, status, drives, info, clear, quit\r\n"
            self.channel.send(fallback_text.encode('utf-8'))
    
    def upload_file(self, source: Union[str, Iterable[str]]):
        """Use scp to copy files to upload_files directory, handles multiple paths"""
        
        def _format_size(num: int) -> str:
            if num > 1024 * 1024:
                return f"{num / (1024 * 1024):.1f} MB"
            if num > 1024:
                return f"{num / 1024:.1f} KB"
            return f"{num} B"
        
        def _prepare_path(path_value: str) -> Optional[str]:
            cleaned = path_value.strip().strip('"').strip("'")
            if not cleaned:
                return None
            if not os.path.isabs(cleaned):
                cleaned = os.path.normpath(os.path.join(self.current_path, cleaned))
            else:
                cleaned = os.path.normpath(cleaned)
            return cleaned
        
        def _copy_single(path_value: str) -> bool:
            normalized = _prepare_path(path_value or "")
            if not normalized:
                self.safe_send("Please provide file path to upload")
                return False
            if not os.path.exists(normalized):
                self.safe_send(f"File not found: {normalized}")
                return False
            if os.path.isdir(normalized):
                self.safe_send("Only single file upload supported, please provide file not directory")
                return False
            
            try:
                self.upload_dir.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                self.safe_send(f"Cannot create upload_files directory: {exc}")
                return False
            
            dest_path = self.upload_dir / os.path.basename(normalized)
            stem, suffix = dest_path.stem, dest_path.suffix
            counter = 1
            while dest_path.exists():
                dest_path = self.upload_dir / f"{stem}_{counter}{suffix}"
                counter += 1
            
            try:
                result = subprocess.run(
                    ["scp", normalized, str(dest_path)],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                stderr = (result.stderr or "").strip()
                if stderr:
                    print(f"SCP Output: {stderr}")
            except FileNotFoundError:
                try:
                    shutil.copy2(normalized, dest_path)
                    size_info = dest_path.stat().st_size
                    self.safe_send(
                        "System cannot find scp, completed using built-in copy process.\r\n"
                        f"File Location: {dest_path}\r\n"
                        f"Size: {_format_size(size_info)}"
                    )
                    return True
                except Exception as exc:
                    self.safe_send(f"Cannot copy file: {exc}")
                    return False
            except subprocess.CalledProcessError as exc:
                message = (exc.stderr or exc.stdout or str(exc)).strip()
                self.safe_send(f"scp transfer failed: {message or 'Unknown Error'}")
                if dest_path.exists():
                    try:
                        dest_path.unlink()
                    except OSError:
                        pass
                return False
            
            size_info = dest_path.stat().st_size
            response = (
                f"Copied file using scp to: {dest_path}\r\n"
                f"Size: {_format_size(size_info)}"
            )
            self.safe_send(response)
            return True
        
        if isinstance(source, str):
            cleaned = source.strip()
            if not cleaned:
                self.safe_send("Usage: upload_file <source_file> [more_files...]")
                return
            _copy_single(cleaned)
            return
        
        try:
            items = list(source)
        except TypeError:
            self.safe_send("Invalid argument format: please provide string or list of strings")
            return
        
        if not items:
            self.safe_send("Please provide at least one file path")
            return
        
        success = 0
        total = len(items)
        for path_value in items:
            if isinstance(path_value, str):
                if _copy_single(path_value):
                    success += 1
            else:
                self.safe_send(f"Ignoring unsupported path type: {path_value!r}")
        
        if total > 1:
            self.safe_send(f"Multi-file transfer completed: {success}/{total} succeeded")
    
    def list_directory(self, path: str):
        """List directory"""
        try:
            response = requests.get(
                f"{self.fastapi_url}/list-directory",
                params={"path": path},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    # Build complete directory list
                    output_text = f"\r\nDirectory: {data['path']}\r\n"
                    output_text += "=" * 50 + "\r\n"
                    
                    # Categorize items
                    dirs = []
                    files = []
                    
                    for item in data['items']:
                        if item['type'] == 'directory':
                            dirs.append(item)
                        else:
                            files.append(item)
                    
                    # Show directories first
                    for item in sorted(dirs, key=lambda x: x['name'].lower()):
                        output_text += f"[DIR]  {item['name']}/\r\n"
                    
                    # Show files then
                    for item in sorted(files, key=lambda x: x['name'].lower()):
                        size = item.get('size', 0)
                        if size > 1024*1024:
                            size_str = f"{size/(1024*1024):.1f}MB"
                        elif size > 1024:
                            size_str = f"{size/1024:.1f}KB"
                        else:
                            size_str = f"{size}B"
                        
                        output_text += f"[FILE] {item['name']} ({size_str})\r\n"
                    
                    output_text += f"\r\nTotal: {len(data['items'])} items ({len(dirs)} 目錄, {len(files)} 檔案)\r\n"
                    
                    self.channel.send(output_text.encode('utf-8'))
                else:
                    error_text = f"Error: {data.get('error', 'Unknown Error')}\r\n"
                    self.channel.send(error_text.encode('utf-8'))
                    
            else:
                error_text = f"HTTP Error: {response.status_code}\r\n"
                self.channel.send(error_text.encode('utf-8'))
                
        except requests.RequestException as e:
            error_text = f"Connection failed: {e}\r\n"
            self.channel.send(error_text.encode('utf-8'))
        except Exception as e:
            error_text = f"Error: {e}\r\n"
            self.channel.send(error_text.encode('utf-8'))
    
    def change_directory(self, path: str):
        """Change directory"""
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
                    success_text = f"Changed to: {self.current_path}\r\n"
                    self.channel.send(success_text.encode('utf-8'))
                else:
                    error_text = f"Cannot change to {path}: {data.get('error', 'Unknown Error')}\r\n"
                    self.channel.send(error_text.encode('utf-8'))
            else:
                error_text = f"Directory does not exist: {path}\r\n"
                self.channel.send(error_text.encode('utf-8'))
                
        except Exception as e:
            error_text = f"Change directory失敗: {e}\r\n"
            self.channel.send(error_text.encode('utf-8'))
    
    def show_current_path(self):
        """Show current path"""
        path_text = f"當前Path: {self.current_path}\r\n"
        self.channel.send(path_text.encode('utf-8'))
    
    def show_user_info(self):
        """Show user info"""
        user_text = f"Current User: {self.username}\r\n"
        self.channel.send(user_text.encode('utf-8'))
    
    def show_status(self):
        """Show status"""
        try:
            response = requests.get(f"{self.fastapi_url}/", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                status_text = (
                    f"\r\nServer Status\r\n"
                    f"=============================\r\n"
                    f"Service Status: {data.get('status', 'Running')}\r\n"
                    f"Current User: {self.username}\r\n"
                    f"當前Path: {self.current_path}\r\n"
                    f"Client IP: {self.client_address[0]}\r\n"
                    f"當前Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\r\n"
                    f"API Status: Normal\r\n"
                    f"=============================\r\n"
                )
                
                self.channel.send(status_text.encode('utf-8'))
            else:
                error_text = "Cannot get Server Status\r\n"
                self.channel.send(error_text.encode('utf-8'))
                
        except Exception as e:
            error_text = f"Failed to get status: {e}\r\n"
            self.channel.send(error_text.encode('utf-8'))
    
    def show_drives(self):
        """Show drives"""
        try:
            response = requests.get(f"{self.fastapi_url}/get-drives", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    drives_text = "\r\nAvailable Drives:\r\n"
                    drives_text += "=" * 30 + "\r\n"
                    
                    for drive in data['drives']:
                        if isinstance(drive, dict):
                            drives_text += f"{drive['drive']}:\\ ({drive.get('type', 'Unknown')})\r\n"
                        else:
                            drives_text += f"{drive}\r\n"
                    
                    drives_text += "=" * 30 + "\r\n"
                    self.channel.send(drives_text.encode('utf-8'))
                else:
                    error_text = "Cannot get drive info\r\n"
                    self.channel.send(error_text.encode('utf-8'))
            else:
                error_text = "Cannot get drive info\r\n"
                self.channel.send(error_text.encode('utf-8'))
                
        except Exception as e:
            error_text = f"Failed to get drives: {e}\r\n"
            self.channel.send(error_text.encode('utf-8'))
    
    def show_file_info(self, path: str):
        """Show file info"""
        try:
            response = requests.get(
                f"{self.fastapi_url}/get-file-info",
                params={"path": path},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    info_text = f"\r\nFile Info: {data['name']}\r\n"
                    info_text += "=============================\r\n"
                    info_text += f"Path: {data['path']}\r\n"
                    info_text += f"Type: {data['type']}\r\n"
                    info_text += f"Size: {data.get('size_human', 'N/A')}\r\n"
                    info_text += f"修改Time: {data['modified']}\r\n"
                    info_text += f"建立Time: {data['created']}\r\n"
                    
                    if data.get('extension'):
                        info_text += f"Extension: {data['extension']}\r\n"
                    
                    info_text += "=============================\r\n"
                    
                    self.channel.send(info_text.encode('utf-8'))
                else:
                    error_text = f"File does not exist: {path}\r\n"
                    self.channel.send(error_text.encode('utf-8'))
            else:
                error_text = f"File does not exist: {path}\r\n"
                self.channel.send(error_text.encode('utf-8'))
                
        except Exception as e:
            error_text = f"Failed to get File Info: {e}\r\n"
            self.channel.send(error_text.encode('utf-8'))
    
    def clear_screen(self):
        """Clear screen"""
        # Send ANSI Clear screen sequence
        self.channel.send(b'\x1b[2J\x1b[H')
    
    def show_goodbye(self):
        """Show goodbye message"""
        goodbye_text = (
            "\r\n=============================\r\n"
            f"Goodbye, {self.username}！\r\n"
            "感謝使用 SSH File Directory Server\r\n"
            "Connection closing...\r\n"
            "=============================\r\n\r\n"
        )
        
        self.channel.send(goodbye_text.encode('utf-8'))
        time.sleep(1)
        self.channel.close()

class SSHServer:
    """SSH Server"""
    
    def __init__(self, host="127.0.0.1", port=2222, fastapi_url="http://localhost:8000"):
        self.host = host
        self.port = port
        self.fastapi_url = fastapi_url
        self.server_key = None
        self.key_file = "ssh_host_key.pem"  # Key file Path
        self.load_or_generate_server_key()
    
    def load_or_generate_server_key(self):
        """Load or generate server key"""
        try:
            # Try loading existing key
            if os.path.exists(self.key_file):
                print(f"Loading existing SSH key: {self.key_file}")
                self.server_key = paramiko.RSAKey.from_private_key_file(self.key_file)
                print("SSH Server key loaded successfully")
            else:
                # Generate new key and save
                print(f"Generating new SSH key: {self.key_file}")
                self.server_key = paramiko.RSAKey.generate(2048)
                self.server_key.write_private_key_file(self.key_file)
                print("SSH Server key generated and saved")
                
        except Exception as e:
            print(f"Failed to process SSH key: {e}")
            # If loading fails, try generating new one
            try:
                print("Trying to generate new key...")
                self.server_key = paramiko.RSAKey.generate(2048)
                self.server_key.write_private_key_file(self.key_file)
                print("New SSH key generated successfully")
            except Exception as e2:
                print(f"Failed to generate SSH key: {e2}")
                sys.exit(1)
    
    def handle_client(self, client_socket, client_address):
        """Handle client connection"""
        print(f"SSH connection from: {client_address}")
        transport = None
        
        try:
            transport = paramiko.Transport(client_socket)
            transport.add_server_key(self.server_key)
            
            # Create SSH shell handler
            ssh_shell = SSHShell("unknown", client_address, self.fastapi_url)
            
            # Start server mode, pass server argument directly
            transport.start_server(server=ssh_shell)
            
            # Wait for client authentication
            channel = transport.accept(timeout=60)
            if channel is None:
                print(f"SSH authentication failed: {client_address}")
                return
            
            print(f"SSH authentication successful: {client_address}, User: {ssh_shell.username}")
            
            # Set channel to shell handler
            ssh_shell.channel = channel
            
            # Run shell session
            ssh_shell.run_shell()
            
        except Exception as e:
            print(f"SSH connection processing error {client_address}: {e}")
        finally:
            try:
                if transport:
                    transport.close()
                if client_socket:
                    client_socket.close()
            except Exception as e:
                print(f"Error closing connection: {e}")
        
        print(f"SSH session ended: {client_address}")
    
    def start(self):
        """Start SSH Server"""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.host, self.port))
            server_socket.listen(5)
            
            print(f"SSH Server started at {self.host}:{self.port}")
            print(f"FastAPI Backend: {self.fastapi_url}")
            print("Waiting for client connection...")
            
            while True:
                try:
                    client_socket, client_address = server_socket.accept()
                    # Create new thread for each client
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except KeyboardInterrupt:
                    print("\nShutting down SSH Server...")
                    break
                except Exception as e:
                    print(f"SSH Server Error: {e}")
                    
        except Exception as e:
            print(f"Failed to start SSH Server: {e}")
        finally:
            try:
                server_socket.close()
            except:
                pass

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="SSH File Directory Server")
    parser.add_argument("--host", default="127.0.0.1", help="Server Address")
    parser.add_argument("--port", type=int, default=2222, help="SSH Port")
    parser.add_argument("--fastapi-url", default="http://localhost:8000", help="FastAPI Server URL")
    
    args = parser.parse_args()
    
    server = SSHServer(args.host, args.port, args.fastapi_url)
    server.start()
