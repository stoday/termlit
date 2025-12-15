"""
Enhanced Telnet Server - Provides Telnet connection and communication with FastAPI server
Uses rich package for beautified interface
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
    print("Need to install rich package: pip install rich")
    # If rich is not available, use basic version
    Console = None

class TelnetServer:
    """Enhanced Telnet Server Class"""
    
    def __init__(self, host: str = "127.0.0.1", port: int = 2323, fastapi_url: str = "http://127.0.0.1:8000"):
        self.host = host
        self.port = port
        self.fastapi_url = fastapi_url
        self.running = False
        self.server_socket: Optional[socket.socket] = None
        
        # Check if rich is supported
        self.rich_enabled = Console is not None
        
    def start(self):
        """Start Telnet Server"""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            print(f"Telnet server started at {self.host}:{self.port}")
            print(f"Connecting to FastAPI server at {self.fastapi_url}")
            print("Waiting for client connection...")
            
            while self.running:
                try:
                    client_socket, address = self.server_socket.accept()
                    print(f"New connection from: {address}")
                    
                    # Create a new thread for each client
                    client_thread = threading.Thread(
                        target=self.handle_client,
                        args=(client_socket, address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error as e:
                    if self.running:
                        print(f"Error accepting connection: {e}")
                        
        except Exception as e:
            print(f"Error starting server: {e}")
        finally:
            self.cleanup()
    
    def stop(self):
        """Stop Telnet Server"""
        print("Stopping Telnet server...")
        self.running = False
        if self.server_socket:
            self.server_socket.close()
    
    def cleanup(self):
        """Clean up resources"""
        if self.server_socket:
            self.server_socket.close()
        print("Telnet server stopped")
    
    def handle_client(self, client_socket: socket.socket, address):
        """Handle client connection - Enhanced version"""
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
            """Send message, supporting Rich formatting"""
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
            # Send enhanced login screen
            if self.rich_enabled and console:
                login_panel = Panel(
                    Text.assemble(
                        ("🔐 ", ""),
                        ("Telnet File Directory Service", "bold cyan"),
                        ("\n\n"),
                        ("Connection Time: ", "bold"),
                        (f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "green"),
                        ("\n"),
                        ("Source IP: ", "bold"),
                        (f"{address[0]}", "yellow"),
                        ("\n\n"),
                        ("Please login first", "bold red"),
                    ),
                    box=box.DOUBLE_EDGE,
                    border_style="bright_blue",
                    title="[bold white]📡 ClockMate Telnet Server 📡[/bold white]",
                    title_align="center"
                )
                console.print(login_panel)
                console.print("\n[bold cyan]Username:[/bold cyan] ", end="")
                send_rich_message("", False)  # Send buffer content
            else:
                # Basic login message
                login_msg = (
                    "\n╭─────────────────────────────────────╮\n"
                    "│     Title                           │\n"
                    f"│    Subtitle: {datetime.now().strftime('%Y-%m-%d %H:%M:%S'):<19}│\n"
                    f"│    Source: {address[0]:<19}  │\n"
                    "╰─────────────────────────────────────╯\n"
                    "Please login first\n"
                    "Username: "
                )
                send_rich_message(login_msg, False)
            
            # Handle login authentication
            authenticated_user = self.authenticate_user(client_socket, address, console, send_rich_message)
            if not authenticated_user:
                send_rich_message("\n❌ Authentication failed, connection closed.\n", False)
                return
            
            # Send enhanced welcome message
            if self.rich_enabled and console:
                welcome_panel = Panel(
                    Text.assemble(
                        ("🎉 ", ""),
                        ("Welcome, ", "bold"),
                        (f"{authenticated_user}", "bold green"),
                        ("!", "bold"),
                        ("\n\n"),
                        ("💡 Type ", ""),
                        ("help", "bold yellow"),
                        (" to see available commands", ""),
                        ("\n"),
                        ("💡 Type ", ""),
                        ("quit", "bold red"),
                        (" or ", ""),
                        ("exit", "bold red"),
                        (" to quit", ""),
                    ),
                    box=box.ROUNDED,
                    border_style="green",
                    title="✅ Login Successful",
                    title_align="center"
                )
                console.print(welcome_panel)
                send_rich_message("", False)
            else:
                welcome_msg = (
                    f"\n✅ Welcome, {authenticated_user}!\n"
                    "Type 'help' to see available commands\n"
                    "Type 'quit' or 'exit' to quit\n"
                )
                send_rich_message(welcome_msg, False)
            
            current_path = "."  # Current path
            
            # Send prompt
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
                    # Receive command
                    data = client_socket.recv(1024).decode('utf-8').strip()
                    if not data:
                        break
                    
                    print(f"Received command from {address} ({authenticated_user}): {data}")
                    
                    # Process command
                    response = self.process_command(data, current_path, authenticated_user, console)
                    
                    # If command changes current path, update it
                    if data.startswith('cd '):
                        new_path = data[3:].strip()
                        if new_path and self.is_valid_directory(new_path):
                            current_path = new_path
                    
                    # Send response
                    if response:
                        send_rich_message(response, self.rich_enabled)
                    
                    # If it's a quit command, close connection
                    if data.lower() in ['quit', 'exit']:
                        break
                    
                    send_prompt()
                        
                except socket.timeout:
                    continue
                except socket.error as e:
                    print(f"Client {address} connection error: {e}")
                    break
                    
        except Exception as e:
            print(f"Error handling client {address}: {e}")
        finally:
            client_socket.close()
            print(f"Client {address} disconnected")
    
    def authenticate_user(self, client_socket: socket.socket, address, console=None, send_message_func=None) -> str:
        """Handle user authentication - Enhanced version"""
        # Default user list
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
                # Receive username
                username_data = client_socket.recv(1024).decode('utf-8').strip()
                if not username_data:
                    return None
                
                username = username_data.replace('\r', '').replace('\n', '')
                
                # Send password prompt
                if self.rich_enabled and console:
                    console.print(f"\n[bold cyan]Password for {username}:[/bold cyan] ", end="")
                    content = console._file.getvalue()
                    if content:
                        client_socket.send(content.encode('utf-8'))
                        console._file.seek(0)
                        console._file.truncate(0)
                else:
                    client_socket.send(f"\nPassword for {username}: ".encode('utf-8'))
                
                # Receive password
                password_data = client_socket.recv(1024).decode('utf-8').strip()
                if not password_data:
                    return None
                
                password = password_data.replace('\r', '').replace('\n', '')
                
                # Verify username and password
                if username in users and users[username] == password:
                    print(f"User {username} logged in successfully from {address}")
                    return username
                else:
                    attempts += 1
                    remaining = max_attempts - attempts
                    
                    if remaining > 0:
                        if self.rich_enabled and console:
                            error_panel = Panel(
                                f"[red]❌ Login Failed![/red]\n[yellow]Remaining attempts: {remaining}[/yellow]",
                                border_style="red",
                                title="Authentication Error"
                            )
                            console.print(error_panel)
                            console.print("\n[bold cyan]Username:[/bold cyan] ", end="")
                            content = console._file.getvalue()
                            if content:
                                client_socket.send(content.encode('utf-8'))
                                console._file.seek(0)
                                console._file.truncate(0)
                        else:
                            error_msg = f"\n❌ Login failed! Remaining attempts: {remaining}\nUsername: "
                            client_socket.send(error_msg.encode('utf-8'))
                        
                        print(f"User {username} failed login from {address} (Attempts remaining: {remaining})")
                    else:
                        if self.rich_enabled and console:
                            final_error = Panel(
                                "[red]❌ Too many login attempts![/red]\n[yellow]Connection will be closed[/yellow]",
                                border_style="red",
                                title="Authentication Failed"
                            )
                            console.print(final_error)
                            content = console._file.getvalue()
                            if content:
                                client_socket.send(content.encode('utf-8'))
                        else:
                            client_socket.send("\n❌ Too many attempts!\n".encode('utf-8'))
                        
                        print(f"Client {address} exceeded login attempt limit")
                        
            except Exception as e:
                print(f"Error during authentication for {address}: {e}")
                break
        
        return None
    
    def process_command(self, command: str, current_path: str, username: str = "unknown", console=None) -> str:
        """Process user command - Enhanced version"""
        original_command = command.strip()
        command = command.strip().lower()
        
        if command == 'help':
            return self.get_help_message(console)
        elif command in ['quit', 'exit']:
            if self.rich_enabled and console:
                goodbye_panel = Panel(
                    f"[green]Goodbye, [bold cyan]{username}[/bold cyan]![/green]\n[yellow]Connection closing...[/yellow]",
                    border_style="green",
                    title="Goodbye"
                )
                console.print(goodbye_panel)
                return console._file.getvalue()
            else:
                return f"Goodbye, {username}! Connection closing.\n"
        elif command == 'pwd':
            if self.rich_enabled and console:
                pwd_panel = Panel(
                    f"[cyan]Current Path:[/cyan] [bold green]{current_path}[/bold green]",
                    border_style="cyan",
                    title="Current Location"
                )
                console.print(pwd_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"Current Path: {current_path}\n> "
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
                    f"[cyan]Current User:[/cyan] [bold green]{username}[/bold green]",
                    border_style="cyan",
                    title="User Info"
                )
                console.print(whoami_panel)
                console.print("\n[bold yellow]>[/bold yellow] ", end="")
                return console._file.getvalue()
            else:
                return f"Current User: {username}\n> "
        else:
            if self.rich_enabled and console:
                unknown_panel = Panel(
                    f"[red]Unknown Command:[/red] [yellow]{original_command}[/yellow]\n[cyan]Type 'help' to see available commands[/cyan]",
                    border_style="red",
                    title="Command Error")