import os
import sys
import platform
import urllib.request
import zipfile
import tempfile
import subprocess
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LLAMA_CPP_VERSION = "b4661"
LLAMA_CPP_BASE_URL = f"https://github.com/ggerganov/llama.cpp/releases/download/{LLAMA_CPP_VERSION}"

class LlamaManager:
    def __init__(self, bin_dir="bin", models_dir="models"):
        self.bin_dir = os.path.abspath(bin_dir)
        self.models_dir = os.path.abspath(models_dir)
        os.makedirs(self.bin_dir, exist_ok=True)
        os.makedirs(self.models_dir, exist_ok=True)
        self.is_windows = platform.system() == "Windows"
        self.is_mac = platform.system() == "Darwin"
        self.server_exe = os.path.join(self.bin_dir, "llama-server.exe" if self.is_windows else "llama-server")

    def download_progress(self, block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = downloaded * 100 / total_size
            sys.stdout.write(f"\rTiến độ tải: {percent:.1f}% ({downloaded/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB)")
            sys.stdout.flush()

    def get_download_url(self, has_cuda=False, has_vulkan=False):
        if self.is_mac:
            if platform.machine() == "arm64":
                return f"{LLAMA_CPP_BASE_URL}/llama-{LLAMA_CPP_VERSION}-bin-macos-arm64.zip"
            else:
                return f"{LLAMA_CPP_BASE_URL}/llama-{LLAMA_CPP_VERSION}-bin-macos-x64.zip"
        elif self.is_windows:
            if has_cuda:
                return f"{LLAMA_CPP_BASE_URL}/llama-{LLAMA_CPP_VERSION}-bin-win-cudart-cu12.2-x64.zip"
            elif has_vulkan:
                return f"{LLAMA_CPP_BASE_URL}/llama-{LLAMA_CPP_VERSION}-bin-win-vulkan-x64.zip"
            else:
                return f"{LLAMA_CPP_BASE_URL}/llama-{LLAMA_CPP_VERSION}-bin-win-avx2-x64.zip"
        else:
            return f"{LLAMA_CPP_BASE_URL}/llama-{LLAMA_CPP_VERSION}-bin-ubuntu-x64.zip"

    def setup_llama_server(self, has_cuda=False, has_vulkan=False):
        if os.path.exists(self.server_exe):
            logger.info("[llama.cpp] Server executable đã có sẵn.")
            return self.server_exe

        url = self.get_download_url(has_cuda, has_vulkan)
        logger.info(f"[llama.cpp] Đang tải llama-server từ {url}...")
        
        zip_path = os.path.join(tempfile.gettempdir(), "llama_cpp.zip")
        try:
            urllib.request.urlretrieve(url, zip_path, reporthook=self.download_progress)
            print("\n[llama.cpp] Đang giải nén...")
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file_info in zip_ref.infolist():
                    extracted_path = zip_ref.extract(file_info, self.bin_dir)
                    if not self.is_windows and file_info.filename.endswith('llama-server'):
                        os.chmod(extracted_path, 0o755)
            
            logger.info("[llama.cpp] Cài đặt thành công!")
        except Exception as e:
            logger.error(f"[llama.cpp] Lỗi khi tải: {e}")
            raise e
        finally:
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except:
                    pass
                
        return self.server_exe

    def download_model(self, model_repo: str, model_filename: str):
        target_path = os.path.join(self.models_dir, model_filename)
        if os.path.exists(target_path):
            logger.info(f"[Model] Mô hình {model_filename} đã có sẵn.")
            return target_path
            
        url = f"https://huggingface.co/{model_repo}/resolve/main/{model_filename}"
        logger.info(f"[Model] Đang tải mô hình từ {url}...")
        
        try:
            urllib.request.urlretrieve(url, target_path, reporthook=self.download_progress)
            print("\n")
            logger.info(f"[Model] Tải thành công: {target_path}")
        except Exception as e:
            logger.error(f"[Model] Lỗi khi tải mô hình: {e}")
            if os.path.exists(target_path):
                os.remove(target_path)
            raise e
                
        return target_path
