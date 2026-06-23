import os
import sys
import platform
import subprocess
import urllib.request
import zipfile
import tarfile
import tempfile
import webbrowser
import time

# Phải import các util từ code hiện tại, PyInstaller sẽ tự bundle các file này
from src.utils.hardware_profiler import ModelZooManager

def download_uv(bin_dir):
    is_win = platform.system() == "Windows"
    uv_exe = os.path.join(bin_dir, "uv.exe" if is_win else "uv")
    if os.path.exists(uv_exe):
        return uv_exe
        
    print("[Launcher] Đang tải uv (Python Package Manager)...")
    
    if is_win:
        url = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip"
    elif platform.system() == "Darwin":
        if platform.machine() == "arm64":
            url = "https://github.com/astral-sh/uv/releases/latest/download/uv-aarch64-apple-darwin.tar.gz"
        else:
            url = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-apple-darwin.tar.gz"
    else:
        url = "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz"
        
    temp_path = os.path.join(tempfile.gettempdir(), "uv_download")
    urllib.request.urlretrieve(url, temp_path)
    
    if url.endswith(".zip"):
        with zipfile.ZipFile(temp_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if file_info.filename.endswith('uv.exe'):
                    file_info.filename = 'uv.exe'
                    zip_ref.extract(file_info, bin_dir)
    else:
        with tarfile.open(temp_path, 'r:gz') as tar_ref:
            for member in tar_ref.getmembers():
                if member.name.endswith('uv'):
                    member.name = 'uv'
                    tar_ref.extract(member, bin_dir)
                    os.chmod(os.path.join(bin_dir, 'uv'), 0o755)
    os.remove(temp_path)
    return uv_exe

def main():
    print("========================================")
    print("   KHỞI CHẠY NOTEBOOKLM MINI STANDALONE ")
    print("========================================")
    
    bin_dir = os.path.abspath("bin")
    os.makedirs(bin_dir, exist_ok=True)
    
    # 1. Cấu hình phần cứng và tải LLM
    manager = ModelZooManager()
    config = manager.auto_setup()
    
    # 2. Chuẩn bị môi trường Python bằng uv
    uv_exe = download_uv(bin_dir)
    
    print("\n[Launcher] Đang thiết lập môi trường Python ảo...")
    subprocess.run([uv_exe, "python", "install", "3.12"], check=True)
    if not os.path.exists(".venv"):
        subprocess.run([uv_exe, "venv", "--python", "3.12"], check=True)
    
    print("\n[Launcher] Đang cài đặt các thư viện cần thiết...")
    subprocess.run([uv_exe, "pip", "install", "-r", "requirements.txt"], check=True)
    
    # 3. Chạy llama-server ngầm
    print("\n[Launcher] Đang khởi động AI Engine (llama.cpp)...")
    llama_exe = config["server_exe"]
    model_path = config["model_path"]
    
    llama_cmd = [llama_exe, "-m", model_path, "--host", "127.0.0.1", "--port", "8080", "-c", "4096"]
    if config["has_cuda"] or config["has_mac_gpu"]:
        llama_cmd.extend(["-ngl", "99"])
    else:
        llama_cmd.extend(["-ngl", "0"])
        
    llama_process = subprocess.Popen(llama_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # 4. Chạy Backend
    print("\n[Launcher] Đang khởi động Backend Server...")
    is_win = platform.system() == "Windows"
    uvicorn_exe = os.path.join(".venv", "Scripts", "uvicorn.exe") if is_win else os.path.join(".venv", "bin", "uvicorn")
    
    backend_cmd = [uvicorn_exe, "src.api.api:app", "--host", "127.0.0.1", "--port", "8000"]
    backend_process = subprocess.Popen(backend_cmd)
    
    # 5. Mở trình duyệt
    print("\n[Launcher] Hoàn tất! Đang mở giao diện trên trình duyệt...")
    time.sleep(3)
    webbrowser.open("http://127.0.0.1:8000")
    
    print("\n[INFO] Nhấn Ctrl+C để tắt toàn bộ hệ thống.")
    try:
        backend_process.wait()
    except KeyboardInterrupt:
        print("\n[INFO] Đang tắt hệ thống...")
        llama_process.terminate()
        backend_process.terminate()

if __name__ == "__main__":
    main()
