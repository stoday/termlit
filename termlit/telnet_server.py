"""
DEPRECATED demo stub

The demo scripts have been moved to the top-level `scripts/` folder to
avoid packaging them into the `termlit` distribution. Please run the
scripts directly from the repository root, for example:

    python ./scripts/telnet_server.py --fastapi-url http://127.0.0.1:8000

This module intentionally contains no runtime logic. It remains here
only to provide a helpful import-time message for older workflows.
"""

def _deprecated_notice():
    raise RuntimeError(
        "Demo scripts have been moved to './scripts/'.\n"
        "Run: python ./scripts/telnet_server.py --fastapi-url http://127.0.0.1:8000"
    )

if __name__ == '__main__':
    _deprecated_notice()
                )
                console.print(unknown_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"Unknown command: {original_command}\nType 'help' to see available commands\n> "
    
    def get_help_message(self, console=None) -> str:
        """Return help message - Enhanced version"""
        if self.rich_enabled and console:
            console.print("[bold cyan]Available Commands:[/bold cyan]")
            console.print("=" * 40)
            
            commands = [
                ("help", "Show this help message"),
                ("ls, dir", "List contents of current directory"),
                ("ls <path>", "List contents of specified directory"),
                ("cd <path>", "Change to specified directory"),
                ("pwd", "Show current path"),
                ("drives", "Show available drives (Windows)"),
                ("info <path>", "Show file/directory details"),
                ("status", "Show server status"),
                ("whoami", "Show current user"),
                ("quit, exit", "Exit connection")
            ]
            
            for cmd, desc in commands:
                console.print(f"[green]{cmd:15}[/green] - {desc}")
            
            console.print(f"\n[bold yellow]Credentials:[/bold yellow]")
            console.print("admin/password123, user/userpass, guest/guest, demo/demo123")
            
            console.print(f"\n[bold blue]Examples:[/bold blue]")
            console.print("ls C:\\Users")
            console.print("cd C:\\")
            console.print("info setup.py")
            
            console.print("\n[bold yellow]>[/bold yellow] ", end="")
            return console._file.getvalue()
        else:
            help_text = """
=== Available Commands ===
help        - Show this help message
ls, dir     - List contents of current directory
ls <path>   - List contents of specified directory
cd <path>   - Change to specified directory
pwd         - Show current path
drives      - Show available drives (Windows)
info <path> - Show file/directory details
status      - Show server status
whoami      - Show current user
quit, exit  - Exit connection

Auth Information:
- Default credentials: admin/password123, user/userpass, guest/guest, demo/demo123
- Max 3 login attempts
- Connection will drop on login failure

Examples:
  ls C:\\Users
  cd C:\\
  info setup.py
  drives

> """
            return help_text
    
    def list_directory(self, path: str, console=None) -> str:
        """List directory contents - Simplified version"""
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
                        console.print(f"[bold cyan]Directory:[/bold cyan] {data['path']}")
                        console.print("=" * 50)
                        
                        # Categorize and sort items
                        dirs = sorted([item for item in data['items'] if item['type'] == 'directory'], 
                                    key=lambda x: x['name'].lower())
                        files = sorted([item for item in data['items'] if item['type'] == 'file'], 
                                     key=lambda x: x['name'].lower())
                        
                        # Show directories
                        for item in dirs:
                            console.print(f"[blue]DIR[/blue]  {item['name']}")
                        
                        # Show files
                        for item in files:
                            size_bytes = item.get('size', 0)
                            if size_bytes < 1024:
                                size_str = f"{size_bytes} B"
                            elif size_bytes < 1024 * 1024:
                                size_str = f"{size_bytes / 1024:.1f} KB"
                            else:
                                size_str = f"{size_bytes / (1024 * 1024):.1f} MB"
                            
                            console.print(f"[green]FILE[/green] {item['name']} [yellow]({size_str})[/yellow]")
                        
                        console.print(f"\n[bold]Total:[/bold] [cyan]{data['total_items']}[/cyan] items")
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        result = f"\nDirectory: {data['path']}\n"
                        result += "=" * 50 + "\n"
                        
                        for item in data['items']:
                            item_type = "[DIR]" if item['type'] == 'directory' else "[FILE]"
                            size = f"({item.get('size', 0)} bytes)" if item['type'] == 'file' else ""
                            result += f"{item_type:8} {item['name']:30} {size}\n"
                        
                        result += f"\nTotal: {data['total_items']} items\n> "
                        return result
                else:
                    if self.rich_enabled and console:
                        console.print(f"[red]Error:[/red] {data.get('error', 'Unknown Error')}")
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        return f"Error: {data.get('error', 'Unknown Error')}\n> "
            else:
                if self.rich_enabled and console:
                    console.print(f"[red]HTTP Error:[/red] {response.status_code}")
                    console.print("\n[bold yellow]>[/bold yellow] ", end="")
                    return console._file.getvalue()
                else:
                    return f"HTTP Error: {response.status_code}\n> "
                
        except requests.RequestException as e:
            if self.rich_enabled and console:
                console.print(f"[red]Failed to connect to FastAPI server:[/red] {str(e)}")
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"Failed to connect to FastAPI server: {e}\n> "
        except Exception as e:
            if self.rich_enabled and console:
                console.print(f"[red]Error processing request:[/red] {str(e)}")
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"Error processing request: {e}\n> "
    
    def change_directory(self, path: str, current_path: str, console=None) -> str:
        """Change directory - Enhanced version"""
        try:
            # Check if target path exists
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
                            f"[green]✓ Successfully changed to:[/green]\n[bold cyan]{data['path']}[/bold cyan]",
                            border_style="green",
                            title="Directory Change"
                        )
                        console.print(success_panel)
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        return f"Changed to: {data['path']}\n> "
                else:
                    if self.rich_enabled and console:
                        error_panel = Panel(
                            f"[red]✗ Failed to change to:[/red] [yellow]{path}[/yellow]\n[red]Error:[/red] {data.get('error', 'Unknown Error')}",
                            border_style="red",
                            title="Change Failed"
                        )
                        console.print(error_panel)
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        return f"Failed to change to {path}: {data.get('error', 'Unknown Error')}\n> "
            else:
                if self.rich_enabled and console:
                    path_error_panel = Panel(
                        f"[red]✗ Path does not exist or access denied:[/red]\n[yellow]{path}[/yellow]",
                        border_style="red",
                        title="Access Error"
                    )
                    console.print(path_error_panel)
                    console.print("\n[bold yellow]>[/bold yellow] ", end="")
                    return console._file.getvalue()
                else:
                    return f"Path does not exist or access denied: {path}\n> "
                
        except requests.RequestException as e:
            if self.rich_enabled and console:
                conn_error_panel = Panel(
                    f"[red]Failed to connect to FastAPI server:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="Server Error"
                )
                console.print(conn_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"Failed to connect to FastAPI server: {e}\n> "
        except Exception as e:
            if self.rich_enabled and console:
                general_error_panel = Panel(
                    f"[red]Error changing directory:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="Unknown Error"
                )
                console.print(general_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"Error changing directory: {e}\n> "
    
    def get_file_info(self, path: str, console=None) -> str:
        """Get file information - Enhanced version"""
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
                        
                        # Create file info table
                        info_table = Table(
                            title=f"📄 File Info: {info['name']}",
                            show_header=True,
                            header_style="bold cyan",
                            border_style="blue"
                        )
                        info_table.add_column("Attribute", style="bold green", width=12)
                        info_table.add_column("Value", style="white", width=40)
                        
                        # Add file information
                        info_table.add_row("Path", info['path'])
                        info_table.add_row("Type", "📁 Directory" if info['type'] == 'directory' else "📄 File")
                        info_table.add_row("Size", info.get('size_human', 'N/A'))
                        info_table.add_row("Modified", info['modified'])
                        info_table.add_row("Created", info['created'])
                        
                        if info.get('extension'):
                            info_table.add_row("Extension", info['extension'])
                        
                        console.print(info_table)
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        result = f"\nFile Info: {info['name']}\n"
                        result += "=" * 40 + "\n"
                        result += f"Path: {info['path']}\n"
                        result += f"Type: {info['type']}\n"
                        result += f"Size: {info.get('size_human', 'N/A')}\n"
                        result += f"Modified: {info['modified']}\n"
                        result += f"Created: {info['created']}\n"
                        if info.get('extension'):
                            result += f"Extension: {info['extension']}\n"
                        result += "\n> "
                        return result
                else:
                    if self.rich_enabled and console:
                        error_panel = Panel(
                            f"[red]Error:[/red] [yellow]{data.get('error', 'Unknown Error')}[/yellow]",
                            border_style="red",
                            title="File Info Error"
                        )
                        console.print(error_panel)
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        return f"Error: {data.get('error', 'Unknown Error')}\n> "
            else:
                if self.rich_enabled and console:
                    http_error_panel = Panel(
                        f"[red]HTTP Error:[/red] [yellow]{response.status_code}[/yellow]",
                        border_style="red",
                        title="Connection Error"
                    )
                    console.print(http_error_panel)
                    console.print("\n[bold yellow]>[/bold yellow] ", end="")
                    return console._file.getvalue()
                else:
                    return f"HTTP Error: {response.status_code}\n> "
                
        except requests.RequestException as e:
            if self.rich_enabled and console:
                conn_error_panel = Panel(
                    f"[red]Failed to connect to FastAPI server:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="Server Error"
                )
                console.print(conn_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"Failed to connect to FastAPI server: {e}\n> "
        except Exception as e:
            if self.rich_enabled and console:
                general_error_panel = Panel(
                    f"[red]Error getting file info:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="Unknown Error"
                )
                console.print(general_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"Error getting file info: {e}\n> "
    
    def get_drives(self, console=None) -> str:
        """Get list of drives - Enhanced version"""
        try:
            response = requests.get(f"{self.fastapi_url}/get-drives", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    if self.rich_enabled and console:
                        from rich.table import Table
                        
                        # Create drives table
                        drives_table = Table(
                            title="💾 Available Drives",
                            show_header=True,
                            header_style="bold cyan",
                            border_style="blue"
                        )
                        drives_table.add_column("Drive", style="bold green", width=8)
                        drives_table.add_column("Type", style="yellow", width=15)
                        drives_table.add_column("Path", style="white", width=20)
                        
                        for drive in data['drives']:
                            if isinstance(drive, dict):
                                drive_letter = drive['drive']
                                drive_type = drive.get('type', 'Unknown')
                                drive_path = f"{drive_letter}:\\"
                                
                                # Select icon based on drive type
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
                        result = "\nAvailable Drives:\n"
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
                            f"[red]Error:[/red] [yellow]{data.get('error', 'Unknown Error')}[/yellow]",
                            border_style="red",
                            title="Drive List Error"
                        )
                        console.print(error_panel)
                        console.print("\n[bold yellow]>[/bold yellow] ", end="")
                        return console._file.getvalue()
                    else:
                        return f"Error: {data.get('error', 'Unknown Error')}\n> "
            else:
                if self.rich_enabled and console:
                    http_error_panel = Panel(
                        f"[red]HTTP Error:[/red] [yellow]{response.status_code}[/yellow]",
                        border_style="red",
                        title="Connection Error"
                    )
                    console.print(http_error_panel)
                    console.print("\n[bold yellow]>[/bold yellow] ", end="")
                    return console._file.getvalue()
                else:
                    return f"HTTP Error: {response.status_code}\n> "
                
        except requests.RequestException as e:
            if self.rich_enabled and console:
                conn_error_panel = Panel(
                    f"[red]Failed to connect to FastAPI server:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="Server Error"
                )
                console.print(conn_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"Failed to connect to FastAPI server: {e}\n> "
        except Exception as e:
            if self.rich_enabled and console:
                general_error_panel = Panel(
                    f"[red]Error getting drive list:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="Unknown Error"
                )
                console.print(general_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"Error getting drive list: {e}\n> "
    
    def get_status(self, username: str = "unknown", console=None) -> str:
        """Get server status - Beautified version"""
        try:
            response = requests.get(f"{self.fastapi_url}/", timeout=5)
            
            if response.status_code == 200:
                data = response.json()
                
                if self.rich_enabled and console:
                    from rich.table import Table
                    import datetime
                    
                    # Create status table
                    status_table = Table(
                        title="⚡ Server Status",
                        show_header=True,
                        header_style="bold cyan",
                        border_style="green"
                    )
                    status_table.add_column("Service", style="bold green", width=15)
                    status_table.add_column("Status", style="white", width=15)
                    status_table.add_column("Details", style="yellow", width=30)
                    
                    # FastAPI Status
                    fastapi_status = data.get('status', 'Unknown')
                    if fastapi_status.lower() == 'ok':
                        status_emoji = "✅"
                        status_color = "[green]Running Normally[/green]"
                    else:
                        status_emoji = "❌"
                        status_color = "[red]Abnormal[/red]"
                    
                    status_table.add_row(
                        "🌐 FastAPI",
                        f"{status_emoji} {status_color}",
                        data.get('message', 'N/A')
                    )
                    
                    # Telnet Status
                    status_table.add_row(
                        "📡 Telnet",
                        "✅ [green]Running[/green]",
                        f"{self.host}:{self.port}"
                    )
                    
                    # User資訊
                    status_table.add_row(
                        "👤 User",
                        "✅ [green]Logged In[/green]",
                        username
                    )
                    
                    # 時間資訊
                    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    status_table.add_row(
                        "🕒 System Time",
                        "✅ [green]Synced[/green]",
                        current_time
                    )
                    
                    console.print(status_table)
                    
                    # 額外資訊面板
                    if data.get('timestamp'):
                        info_panel = Panel(
                            f"[cyan]FastAPI Timestamp:[/cyan] {data['timestamp']}",
                            border_style="blue",
                            title="額外資訊"
                        )
                        console.print(info_panel)
                    
                    console.print("\n[bold yellow]>[/bold yellow] ", end="")
                    return console._file.getvalue()
                else:
                    result = f"\nFastAPI Server Status: {data.get('status', 'Unknown')}\n"
                    result += f"Service訊息: {data.get('message', 'N/A')}\n"
                    result += f"時間戳: {data.get('timestamp', 'N/A')}\n"
                    result += f"\nTelnet Service器: Running於 {self.host}:{self.port}\n"
                    result += f"Current User: {username}\n"
                    result += "\n> "
                    return result
            else:
                if self.rich_enabled and console:
                    error_panel = Panel(
                        f"[red]FastAPI Service器無回應[/red]\n[yellow]HTTP Status碼: {response.status_code}[/yellow]",
                        border_style="red",
                        title="Server Error"
                    )
                    console.print(error_panel)
                    console.print("\n[bold yellow]>[/bold yellow] ", end="")
                    return console._file.getvalue()
                else:
                    return f"FastAPI Service器無回應 (HTTP {response.status_code})\n> "
                
        except requests.RequestException as e:
            if self.rich_enabled and console:
                conn_error_panel = Panel(
                    f"[red]無法連接到 FastAPI Service器:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="連接Error"
                )
                console.print(conn_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"無法連接到 FastAPI Service器: {e}\n> "
        except Exception as e:
            if self.rich_enabled and console:
                general_error_panel = Panel(
                    f"[red]獲取Status時發生Error:[/red]\n[yellow]{str(e)}[/yellow]",
                    border_style="red",
                    title="Unknown Error"
                )
                console.print(general_error_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"獲取Status時發生Error: {e}\n> "
    
    def is_valid_directory(self, path: str) -> bool:
        """檢查Path是否為有效目錄"""
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
    """Start Telnet Server"""
    server = TelnetServer(host, port, fastapi_url)
    
    try:
        server.start()
    except KeyboardInterrupt:
        print("\n收到中斷信號，正在停止Service器...")
        server.stop()
    except Exception as e:
        print(f"Server Error: {e}")
        server.stop()

if __name__ == "__main__":
    # 等待 FastAPI Service器啟動
    print("等待 FastAPI Service器啟動...")
    time.sleep(2)
    start_telnet_server()