import platform
import psutil
import subprocess
import sys
import os
import shutil

# Ép HuggingFace tải Cache vào ổ D thay vì ổ C và cấm kết nối Internet
os.environ["HF_HOME"] = os.path.join(os.getcwd(), "cache", "huggingface")
# os.environ["HF_HUB_OFFLINE"] = "1" # Bỏ comment nếu muốn ép offline

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from src.utils.llama_manager import LlamaManager

class ModelZooManager:
    def __init__(self):
        self.os_name = platform.system()
        self.total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
        
        # Cảm biến đo dung lượng ổ cứng hiện tại
        total, used, free = shutil.disk_usage(os.getcwd())
        self.free_disk_gb = free / (1024 ** 3)
        
        self.vram_gb = 0
        self.has_cuda = False
        self._detect_gpu()

    def _detect_gpu(self):
        if self.os_name in ['Windows', 'Linux']:
            try:
                result = subprocess.run(['nvidia-smi', '--query-gpu=memory.total', '--format=csv,noheader,nounits'], 
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if result.returncode == 0:
                    self.vram_gb = sum(int(x) for x in result.stdout.strip().split('\n')) / 1024
                    self.has_cuda = True
                    return
            except Exception:
                pass
            
            try:
                if self.os_name == 'Windows':
                    result = subprocess.run(['wmic', 'path', 'win32_VideoController', 'get', 'AdapterRAM'], 
                                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    if result.returncode == 0:
                        lines = [line.strip() for line in result.stdout.split('\n') if line.strip() and line.strip().isdigit()]
                        if lines:
                            self.vram_gb = sum(int(x) for x in lines) / (1024 ** 3)
            except Exception:
                pass
        elif self.os_name == 'Darwin':
            self.vram_gb = self.total_ram_gb * 0.75

    def auto_setup(self):
        print("\n" + "="*50)
        print("🤖 NOTEBOOKLM MINI - KHỞI TẠO LẦN ĐẦU TỰ ĐỘNG 🤖")
        print("="*50)
        print(f"📌 [Phân tích hệ thống]")
        print(f" - Hệ điều hành: {self.os_name}")
        print(f" - RAM vật lý: {self.total_ram_gb:.1f} GB")
        print(f" - VRAM (Card đồ hoạ): {self.vram_gb:.1f} GB")
        print(f" - Ổ đĩa trống: {self.free_disk_gb:.1f} GB")
        print("="*50)
        
        # LỰA CHỌN LLM
        models_map = {
            "1": {"repo": "Qwen/Qwen2.5-14B-Instruct-GGUF", "file": "qwen2.5-14b-instruct-q4_k_m.gguf"},
            "2": {"repo": "Qwen/Qwen2.5-7B-Instruct-GGUF", "file": "qwen2.5-7b-instruct-q4_k_m.gguf"},
            "3": {"repo": "Qwen/Qwen2.5-3B-Instruct-GGUF", "file": "qwen2.5-3b-instruct-q4_k_m.gguf"},
            "4": {"repo": "Qwen/Qwen2.5-0.5B-Instruct-GGUF", "file": "qwen2.5-0.5b-instruct-q4_k_m.gguf"}
        }

        print("\n🧠 LỰA CHỌN BỘ NÃO AI (LLM)")
        print(" Hệ thống hỗ trợ nhiều kích cỡ LLM. Hãy chọn mức phù hợp với máy của bạn:")
        print("  [1] Qwen 2.5 (14B) - Cực thông minh | Tốn ~9.0GB ổ cứng | Khuyên dùng nếu VRAM > 12GB")
        print("  [2] Qwen 2.5 (7B)  - Thông minh     | Tốn ~4.5GB ổ cứng | Khuyên dùng nếu VRAM > 6GB")
        print("  [3] Qwen 2.5 (3B)  - Cân bằng       | Tốn ~2.0GB ổ cứng | Phù hợp Laptop tầm trung")
        print("  [4] Qwen 2.5 (0.5B)- Siêu nhẹ       | Tốn ~0.5GB ổ cứng | Chạy mượt trên mọi máy")
        
        while True:
            choice_llm = input("👉 Nhập lựa chọn của bạn (1-4) [Mặc định: 3]: ").strip()
            if not choice_llm: choice_llm = "3"
            
            if choice_llm in models_map:
                selected_model = models_map[choice_llm]
                break
            else:
                print("⚠️ Lựa chọn không hợp lệ, vui lòng nhập lại!")

        # LỰA CHỌN EMBEDDING MODEL
        print("\n📚 LỰA CHỌN MÔ HÌNH NHÚNG (EMBEDDING)")
        print(" Hệ thống cần một mô hình để đọc và tìm kiếm văn bản của bạn:")
        print("  [1] GreenNode-Embedding-Large (Nặng ~1.2GB) - Siêu chính xác | Khuyên dùng nếu RAM > 8GB")
        print("  [2] Vietnamese-sBERT (Nhẹ ~100MB)           - Khá chính xác  | Chạy mượt trên mọi máy")
        
        while True:
            choice_emb = input("👉 Nhập lựa chọn của bạn (1-2) [Mặc định: 1]: ").strip()
            if not choice_emb: choice_emb = "1"
            
            if choice_emb in ["1", "2"]:
                break
            else:
                print("⚠️ Lựa chọn không hợp lệ, vui lòng nhập lại!")
                
        embedding_model = "GreenNode/GreenNode-Embedding-Large-VN-Mixed-V1" if choice_emb == "1" else "keepitreal/vietnamese-sbert"
        
        # LỰA CHỌN RERANKER MODEL
        print("\n🔍 LỰA CHỌN MÔ HÌNH CHẤM ĐIỂM (RERANKER)")
        print(" Giúp AI lọc ra kết quả tìm kiếm chính xác nhất trước khi trả lời:")
        print("  [1] BGE-Reranker-v2-m3 (Nặng ~1.1GB)     - Chuẩn xác | Khuyên dùng nếu RAM > 8GB")
        print("  [2] mMiniLMv2-L12-H384 (Nhẹ ~130MB)      - Vừa đủ xài| Chạy mượt trên mọi máy")
        
        while True:
            choice_reranker = input("👉 Nhập lựa chọn của bạn (1-2) [Mặc định: 1]: ").strip()
            if not choice_reranker: choice_reranker = "1"
            
            if choice_reranker in ["1", "2"]:
                break
            else:
                print("⚠️ Lựa chọn không hợp lệ, vui lòng nhập lại!")
                
        reranker_model = "BAAI/bge-reranker-v2-m3" if choice_reranker == "1" else "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"

        # Ghi cấu hình vào .env
        env_path = os.path.join(os.getcwd(), ".env")
        env_content = ""
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                env_content = f.read()
                
        import re
        if "RAG_EMBEDDING_MODEL" in env_content:
            env_content = re.sub(r'RAG_EMBEDDING_MODEL=.*', f'RAG_EMBEDDING_MODEL={embedding_model}', env_content)
        else:
            env_content += f"\nRAG_EMBEDDING_MODEL={embedding_model}\n"
            
        if "RAG_RERANKER_MODEL" in env_content:
            env_content = re.sub(r'RAG_RERANKER_MODEL=.*', f'RAG_RERANKER_MODEL={reranker_model}', env_content)
        else:
            env_content += f"RAG_RERANKER_MODEL={reranker_model}\n"
            
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)

        print("\n⏳ Đang tiến hành thiết lập hệ thống theo yêu cầu của bạn...")
        
        # 1. Sinh file requirements.txt
        req_base_path = os.path.join(os.getcwd(), "requirements-base.txt")
        req_out_path = os.path.join(os.getcwd(), "requirements.txt")
        
        with open(req_base_path, "r", encoding="utf-8") as f:
            req_content = f.read()
            
        pytorch_mode = "gpu" if self.has_cuda else "cpu"
        
        if pytorch_mode == "cpu":
            if self.os_name == "Darwin":
                print("📦 Đã chọn: Cài đặt PyTorch Native (Apple Metal)")
                req_content += "\n# --- PyTorch Apple Metal ---\n"
                req_content += "torch>=2.0.0\n"
            else:
                print("📦 Đã chọn: Cài đặt PyTorch CPU-Only (Diet Plan)")
                req_content += "\n# --- PyTorch CPU-Only (Diet Plan) ---\n"
                req_content += "--extra-index-url https://download.pytorch.org/whl/cpu\n"
                req_content += "torch==2.6.0+cpu\n"
                req_content += "torchvision==0.21.0+cpu\n"
                req_content += "torchaudio==2.6.0+cpu\n"
        else:
            print("📦 Đã chọn: Cài đặt PyTorch Full Speed (NVIDIA GPU)")
            req_content += "\n# --- PyTorch Full Speed ---\n"
            req_content += "torch>=2.0.0\n"
            
        with open(req_out_path, "w", encoding="utf-8") as f:
            f.write(req_content)
            
        # 2. Cài đặt llama.cpp và Model
        llama = LlamaManager()
        server_exe = llama.setup_llama_server(has_cuda=False, has_vulkan=self.has_cuda)
        model_path = llama.download_model(selected_model["repo"], selected_model["file"])
        
        print("✅ Đã tạo cấu hình và tải AI engine hoàn tất!")
        
        return {
            "server_exe": server_exe,
            "model_path": model_path,
            "has_cuda": self.has_cuda,
            "has_mac_gpu": self.os_name == 'Darwin'
        }

if __name__ == "__main__":
    manager = ModelZooManager()
    manager.auto_setup()
