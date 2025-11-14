"""
檔案目錄服務啟動器 - 啟動 Telnet 與 SSH 服務器，需自行提供 FastAPI 後端
"""
import os
import sys
import time
import threading
import subprocess


def start_telnet_server(host: str, port: int, fastapi_url: str):
    """啟動 Telnet 服務器"""
    print(f"正在啟動 Telnet 服務器 (FastAPI 後端: {fastapi_url})...")
    
    try:
        from telnet_server import start_telnet_server as telnet_entry
        telnet_entry(host=host, port=port, fastapi_url=fastapi_url)
    except ImportError as e:
        print(f"導入 Telnet 服務器失敗: {e}")
        print("請確認已安裝所需的依賴套件")
    except Exception as e:
        print(f"啟動 Telnet 服務器時發生錯誤: {e}")


def start_ssh_server(host: str, port: int, fastapi_url: str):
    """啟動 SSH 服務器"""
    print(f"正在啟動 SSH 服務器 (FastAPI 後端: {fastapi_url})...")
    
    try:
        from ssh_server_plain import SSHServer
        ssh_server = SSHServer(host=host, port=port, fastapi_url=fastapi_url)
        ssh_server.start()
    except ImportError as e:
        print(f"導入 SSH 服務器失敗: {e}")
        print("可能需要安裝 paramiko: pip install paramiko")
    except Exception as e:
        print(f"啟動 SSH 服務器時發生錯誤: {e}")

def check_dependencies():
    """檢查必要的依賴套件"""
    required_packages = ["requests", "rich"]
    optional_packages = {"paramiko": "SSH 功能"}
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
        print(f"缺少必要套件: {', '.join(missing_packages)}")
        print("請執行以下命令安裝依賴:")
        print("pip install -r requirements.txt")
        return False
    
    if missing_optional:
        print(f"缺少選用套件: {', '.join(missing_optional)}")
        print("這些功能將無法使用")
    
    return True

def main():
    """主函數"""
    import argparse
    
    parser = argparse.ArgumentParser(description="檔案目錄服務啟動器")
    parser.add_argument("--mode", choices=["all", "telnet", "ssh"], 
                       default="all", help="啟動模式 (預設: all)")
    parser.add_argument("--ssh-port", type=int, default=2222, help="SSH 埠號 (預設: 2222)")
    parser.add_argument("--telnet-port", type=int, default=2323, help="Telnet 埠號 (預設: 2323)")
    parser.add_argument(
        "--fastapi-url",
        default="http://127.0.0.1:8000",
        help="FastAPI 服務器 URL（請自行啟動）"
    )
    
    args = parser.parse_args()
    
    print("=== 檔案目錄服務啟動器 ===")
    print(f"工作目錄: {os.getcwd()}")
    print(f"Python 版本: {sys.version}")
    print(f"啟動模式: {args.mode}")
    
    # 檢查依賴套件
    if not check_dependencies():
        return 1
    
    print("\n正在啟動服務...")
    
    services_info = []
    
    services_info.append(f"FastAPI 後端 (自行提供): {args.fastapi_url}")
    
    if args.mode in ["all", "telnet"]:
        services_info.append(f"Telnet 服務器: 127.0.0.1:{args.telnet_port}")
    
    if args.mode in ["all", "ssh"]:
        services_info.append(f"SSH 服務器: 127.0.0.1:{args.ssh_port}")
        services_info.append("SSH 測試連接: ssh admin@127.0.0.1 -p 2222")
        services_info.append("SSH 預設密碼: password123")
    
    for info in services_info:
        print(info)
    
    print("\n請先啟動 FastAPI 服務器，或指定現有的 --fastapi-url 供 Telnet/SSH 使用")
    
    print("\n按 Ctrl+C 停止所有服務\n")
    
    try:
        threads = []
        
        # 啟動 Telnet 服務器
        if args.mode in ["all", "telnet"]:
            telnet_thread = threading.Thread(
                target=start_telnet_server,
                kwargs={
                    "host": "127.0.0.1",
                    "port": args.telnet_port,
                    "fastapi_url": args.fastapi_url,
                },
            )
            telnet_thread.daemon = True
            telnet_thread.start()
            threads.append(telnet_thread)
        
        # 啟動 SSH 服務器
        if args.mode in ["all", "ssh"]:
            try:
                import paramiko
                ssh_thread = threading.Thread(
                    target=start_ssh_server,
                    kwargs={
                        "host": "0.0.0.0",
                        "port": args.ssh_port,
                        "fastapi_url": args.fastapi_url,
                    },
                )
                ssh_thread.daemon = True
                ssh_thread.start()
                threads.append(ssh_thread)
            except ImportError:
                print("警告: 無法啟動 SSH 服務器，缺少 paramiko 套件")
                if args.mode == "ssh":
                    print("請執行: pip install paramiko")
                    return 1
        
        # 保持主線程運行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n收到停止信號，正在關閉服務...")
        print("所有服務已停止")
        return 0
    except Exception as e:
        print(f"啟動服務時發生錯誤: {e}")
        return 1

def install_dependencies():
    """安裝依賴套件"""
    print("正在安裝依賴套件...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("依賴套件安裝完成")
        return True
    except subprocess.CalledProcessError as e:
        print(f"安裝依賴套件失敗: {e}")
        return False

if __name__ == "__main__":
    # 如果指定了 --install 參數，先安裝依賴
    if len(sys.argv) > 1 and sys.argv[1] == "--install":
        if install_dependencies():
            print("請重新執行程式啟動服務")
        sys.exit(0)
    
    sys.exit(main())
