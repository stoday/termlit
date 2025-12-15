"""
File Directory Service Launcher - Starts FastAPI, Telnet, and SSH servers simultaneously
"""
import os
import sys
import time
import threading
import subprocess
from pathlib import Path

# def start_fastapi_server():
#     """啟動 FastAPI 服務器"""
#     print("正在啟動 FastAPI 服務器...")
    
#     try:
#         # 導入並啟動 FastAPI 服務器
#         from fastapi_server import start_server
#         start_server(host="127.0.0.1", port=8000)
#     except ImportError as e:
#         print(f"導入 FastAPI 服務器失敗: {e}")
#         print("請確認已安裝所需的依賴套件: pip install -r requirements.txt")
#     except Exception as e:
#         print(f"啟動 FastAPI 服務器時發生Error: {e}")

def start_telnet_server():
    """Start Telnet Server"""
    print("Waiting for FastAPI server to start...")
    time.sleep(3)  # Wait for FastAPI server to fully start
    
    print("Starting Telnet server...")
    
    try:
        from telnet_server import start_telnet_server
        start_telnet_server(host="127.0.0.1", port=2323, fastapi_url="http://127.0.0.1:8000")
    except ImportError as e:
        print(f"Failed to import Telnet server: {e}")
        print("Please ensure required dependencies are installed")
    except Exception as e:
        print(f"Error starting Telnet server: {e}")

def start_ssh_server():
    """Start SSH Server"""
    print("Waiting for FastAPI server to start...")
    time.sleep(3)  # Wait for FastAPI server to fully start
    
    print("Starting SSH server (Plain text version)...")
    
    try:
        from ssh_server_plain import SSHServer
        ssh_server = SSHServer(host="0.0.0.0", port=2222, fastapi_url="http://127.0.0.1:8000")
        ssh_server.start()
    except ImportError as e:
        print(f"Failed to import SSH server: {e}")
        print("You may need to install paramiko: pip install paramiko")
    except Exception as e:
        print(f"Error starting SSH server: {e}")

def check_dependencies():
    """Check required dependencies"""
    required_packages = ["fastapi", "uvicorn", "requests"]
    optional_packages = {"paramiko": "SSH feature"}
    missing_packages = []
    missing_optional = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    for package, feature in optional_packages.items():
        try:
            __import__(package)
        except ImportError:
            missing_optional.append(f"{package} ({feature})")
    
    if missing_packages:
        print(f"Missing required packages: {', '.join(missing_packages)}")
        print("Please run the following command to install dependencies:")
        print("pip install -r requirements.txt")
        return False
    
    if missing_optional:
        print(f"Missing optional packages: {', '.join(missing_optional)}")
        print("These features will not be available")
    
    return True

def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description="File Directory Service Launcher")
    parser.add_argument("--mode", choices=["all", "api-only", "telnet", "ssh"], 
                       default="all", help="Launch mode (default: all)")
    parser.add_argument("--ssh-port", type=int, default=2222, help="SSH Port (default: 2222)")
    parser.add_argument("--telnet-port", type=int, default=2323, help="Telnet Port (default: 2323)")
    parser.add_argument("--api-port", type=int, default=8000, help="FastAPI Port (default: 8000)")
    
    args = parser.parse_args()
    
    print("=== File Directory Service Launcher ===")
    print(f"Working Directory: {os.getcwd()}")
    print(f"Python Version: {sys.version}")
    print(f"Launch Mode: {args.mode}")
    
    # Check dependencies
    if not check_dependencies():
        return 1
    
    print("\nStarting services...")
    
    services_info = []
    
    if args.mode in ["all", "api-only"]:
        services_info.append(f"FastAPI Server: http://127.0.0.1:{args.api_port}")
        services_info.append(f"API Docs: http://127.0.0.1:{args.api_port}/docs")
    
    if args.mode in ["all", "telnet"]:
        services_info.append(f"Telnet Server: 127.0.0.1:{args.telnet_port}")
    
    if args.mode in ["all", "ssh"]:
        services_info.append(f"SSH Server: 127.0.0.1:{args.ssh_port}")
        services_info.append("SSH Test Connection: ssh admin@127.0.0.1 -p 2222")
        services_info.append("SSH Default Password: password123")
    
    for info in services_info:
        print(info)
    
    print("\nPress Ctrl+C to stop all services\n")
    
    try:
        threads = []
        
        # # Start FastAPI Server (SSH and Telnet need it)
        # if args.mode in ["all", "api-only", "telnet", "ssh"]:
        #     fastapi_thread = threading.Thread(target=start_fastapi_server)
        #     fastapi_thread.daemon = True
        #     fastapi_thread.start()
        #     threads.append(fastapi_thread)
        
        # Start Telnet Server
        if args.mode in ["all", "telnet"]:
            telnet_thread = threading.Thread(target=start_telnet_server)
            telnet_thread.daemon = True
            telnet_thread.start()
            threads.append(telnet_thread)
        
        # Start SSH Server
        if args.mode in ["all", "ssh"]:
            try:
                import paramiko
                ssh_thread = threading.Thread(target=start_ssh_server)
                ssh_thread.daemon = True
                ssh_thread.start()
                threads.append(ssh_thread)
            except ImportError:
                print("Warning: Cannot start SSH server, paramiko package missing")
                if args.mode == "ssh":
                    print("Please run: pip install paramiko")
                    return 1
        
        # Keep main thread running
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\nReceived stop signal, shutting down services...")
        print("All services stopped")
        return 0
    except Exception as e:
        print(f"Error starting services: {e}")
        return 1

def install_dependencies():
    """Install dependencies"""
    print("Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("Dependencies installed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to install dependencies: {e}")
        return False

if __name__ == "__main__":
    # If --install argument is provided, install dependencies first
    if len(sys.argv) > 1 and sys.argv[1] == "--install":
        if install_dependencies():
            print("Please run the program again to start services")
        sys.exit(0)
    
    sys.exit(main())