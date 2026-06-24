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
<<<<<<< HEAD
        self.has_mps = False
        self.gpu_names = []
        self._detect_gpu()

    def _detect_gpu(self):
        self.gpu_names = []
        
        # 1. Phát hiện GPU trên Windows bằng wmic (để lấy danh sách đầy đủ bao gồm Intel, AMD, NVIDIA)
        if platform.system() == "Windows":
            try:
                import subprocess
                # Lấy tên GPU
                result_name = subprocess.run(["wmic", "path", "win32_VideoController", "get", "Name"], capture_output=True, text=True)
                if result_name.returncode == 0:
                    self.gpu_names = [line.strip() for line in result_name.stdout.split('\n')[1:] if line.strip()]
                
                # Lấy AdapterRAM
                result_ram = subprocess.run(["wmic", "path", "win32_VideoController", "get", "AdapterRAM"], capture_output=True, text=True)
                if result_ram.returncode == 0:
                    lines = [line.strip() for line in result_ram.stdout.split('\n') if line.strip() and line.strip().isdigit()]
                    if lines:
                        max_ram_bytes = max(int(ram) for ram in lines)
                        self.vram_gb = max_ram_bytes / (1024**3)
            except Exception:
                pass

        # 2. Thử dùng nvidia-smi để lấy VRAM chính xác hơn của NVIDIA (nếu có)
        try:
            import subprocess
            result = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True)
            if result.returncode == 0:
                parts = result.stdout.strip().split('\n')[0].split(',')
                gpu_name = parts[0].strip()
                vram_mb = int(parts[1].strip())
                self.vram_gb = vram_mb / 1024
                self.has_cuda = True
                if gpu_name not in self.gpu_names:
                    self.gpu_names.append(gpu_name)
        except Exception:
            pass

        # 3. Phát hiện Apple Silicon trên macOS
        if platform.system() == "Darwin":
            try:
                import platform as pf
                if "arm" in pf.machine().lower() or "arm" in pf.processor().lower():
                    self.has_mps = True
                    self.gpu_names.append("Apple Silicon GPU (Metal)")
            except Exception:
                pass

        # 4. Kiểm tra xem có phải card NVIDIA không để gán has_cuda
        if any("nvidia" in name.lower() for name in self.gpu_names):
            self.has_cuda = True

    def get_tier(self):
        if self.vram_gb > 16:
            return 1
        elif self.vram_gb > 8:
            return 2
        elif self.vram_gb >= 4:
            return 3
        else:
            return 4

    def get_recommended_config(self):
        tier = self.get_tier()
        config = MODEL_ZOO[tier].copy()
        return config

    def check_build_tools(self) -> bool:
        """Kiểm tra xem C++ Build Tools có được cài đặt không."""
        if platform.system() != "Windows":
            return True # Linux/Mac thường có sẵn GCC/Clang
        try:
            # Tìm vswhere.exe
            vswhere_path = os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "Microsoft Visual Studio", "Installer", "vswhere.exe")
            if os.path.exists(vswhere_path):
                result = subprocess.run([vswhere_path, "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "installationPath"], capture_output=True, text=True)
                if result.stdout.strip():
                    return True
        except Exception:
            pass
        return False

    def setup_layer_1_and_2(self) -> bool:
        """Thử cài đặt thư viện llama-cpp-python. Trả về True nếu thành công."""
        try:
            import huggingface_hub
        except ImportError:
            print("[Auto-Setup] Đang cài đặt thư viện huggingface_hub...")
            subprocess.run(["uv", "pip", "install", "huggingface-hub"], check=True)
            
        has_tools = self.check_build_tools()
        
        try:
            import llama_cpp
            return True
        except ImportError:
            if has_tools:
                print("[Lớp 1] Phát hiện C++ Build Tools! Đang tự biên dịch llama-cpp-python từ mã nguồn để đạt hiệu năng tối đa...")
                try:
                    subprocess.run(["uv", "pip", "install", "llama-cpp-python", "--no-binary", "llama-cpp-python"], check=True)
                    return True
                except Exception as e:
                    print(f"[Lớp 1] Biên dịch thất bại: {e}. Đang chuyển sang Lớp 2...")
            
            print("[Lớp 2] Đang cài đặt llama-cpp-python (Pre-compiled wheels)...")
            try:
                subprocess.run(["uv", "pip", "install", "llama-cpp-python", "--extra-index-url", "https://abetlen.github.io/llama-cpp-python/whl/cpu"], check=True)
                return True
            except Exception as e:
                print(f"[Lớp 2] Cài đặt Pre-compiled thất bại: {e}")
                return False

    def test_llama_cpp(self, model_path: str) -> bool:
        """Kiểm thử khởi tạo mô hình. Trả về True nếu khởi chạy thành công (không bị lỗi AVX2)."""
        print("[Kiểm thử Lớp 2] Đang test khởi tạo mô hình bằng llama_cpp...")
        try:
            import ctypes
            # Thử gọi Llama
            from llama_cpp import Llama
            llm = Llama(model_path=model_path, n_gpu_layers=0, n_ctx=128, verbose=False)
            print("[Kiểm thử Lớp 2] THÀNH CÔNG! Lớp 1/2 chạy hoàn hảo.")
            return True
        except OSError as e:
            if "0xc000001d" in str(e) or "illegal instruction" in str(e).lower():
                print(f"[Kiểm thử Lớp 2] THẤT BẠI! Xung đột tập lệnh CPU (Lỗi 0xc000001d - thường do Wheel chứa AVX-512 mà CPU không hỗ trợ): {e}")
            else:
                print(f"[Kiểm thử Lớp 2] THẤT BẠI! Lỗi hệ thống: {e}")
            return False
        except Exception as e:
            print(f"[Kiểm thử Lớp 2] THẤT BẠI! Lỗi không xác định: {e}")
            return False

    def check_and_install_model(self, repo_id: str, filename: str) -> str:
        """Tải model từ HF về thư mục /models và trả về đường dẫn."""
        models_dir = os.path.join(os.getcwd(), "models")
        os.makedirs(models_dir, exist_ok=True)
        
        target_path = os.path.join(models_dir, filename)
        if os.path.exists(target_path):
            print(f"\n[Model Manager] Đã tìm thấy mô hình Offline: \033[92m{filename}\033[0m")
            return target_path
            
        print(f"\n[Model Manager] Đang tải mô hình GGUF (Cần WiFi): \033[92m{filename}\033[0m")
        from huggingface_hub import hf_hub_download
        try:
            model_path = hf_hub_download(repo_id=repo_id, filename=filename, local_dir=models_dir, local_dir_use_symlinks=False)
            return model_path
        except Exception as e:
            print(f"[Lỗi] Quá trình tải {filename} thất bại: {str(e)}")
            return ""

    def setup_ollama_portable(self, model_tag: str):
        """LỚP 3: Tự động tải Ollama Portable, bật server ngầm, và pull model."""
        print("\n[LỚP 3 - Cứu cánh] Kích hoạt chế độ tải Ollama Portable dành cho CPU cũ...")
        bin_dir = os.path.join(os.getcwd(), "bin")
        os.makedirs(bin_dir, exist_ok=True)
        ollama_exe = os.path.join(bin_dir, "ollama.exe")
        
        # 1. Tải Ollama Portable nếu chưa có
        if not os.path.exists(ollama_exe):
            print("[Lớp 3] Đang tải Ollama Portable (Khoảng 150MB). Vui lòng đợi...")
            import urllib.request
            import zipfile
            import tempfile
            import sys
=======
        self.gpu_name = "Unknown"
        self.recommended_tier = 2  # Mặc định: Thử Lớp 2 (Native)
        self._detect_gpu()

    def _detect_gpu(self):
        """Nhận diện phần cứng GPU: Tên card, VRAM, và phân Lớp (Tier) tự động."""
        if self.os_name in ['Windows', 'Linux']:
            # --- Bước 1: Thử nhận diện NVIDIA qua nvidia-smi ---
            try:
                result = subprocess.run(
                    ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'], 
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    if lines:
                        parts = lines[0].split(',')
                        self.gpu_name = parts[0].strip()
                        self.vram_gb = sum(int(line.split(',')[1].strip()) for line in lines) / 1024
                        self.has_cuda = True
                        self.recommended_tier = 2  # NVIDIA -> Thử Lớp 2 (llama-server CUDA)
                        return
            except Exception:
                pass
>>>>>>> f9596404713f72a50f34b3f444ecafca4bfa705c
            
            # --- Bước 2: Không phải NVIDIA -> Đọc tên Card qua WMIC (Windows) ---
            try:
                if self.os_name == 'Windows':
                    # Đọc tên Card đồ họa
                    name_result = subprocess.run(
                        ['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                    )
                    if name_result.returncode == 0:
                        name_lines = [line.strip() for line in name_result.stdout.split('\n') 
                                      if line.strip() and line.strip().lower() != 'name']
                        if name_lines:
                            self.gpu_name = name_lines[0]
                    
                    # Đọc VRAM
                    ram_result = subprocess.run(
                        ['wmic', 'path', 'win32_VideoController', 'get', 'AdapterRAM'], 
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                    )
                    if ram_result.returncode == 0:
                        ram_lines = [line.strip() for line in ram_result.stdout.split('\n') 
                                     if line.strip() and line.strip().isdigit()]
                        if ram_lines:
                            self.vram_gb = sum(int(x) for x in ram_lines) / (1024 ** 3)
                    
                    # Phân Lớp dựa trên tên Card
                    gpu_lower = self.gpu_name.lower()
                    if any(keyword in gpu_lower for keyword in ['intel', 'iris', 'uhd']):
                        self.recommended_tier = 3  # Intel iGPU -> Đi thẳng Lớp 3 (Ollama Vulkan)
                    elif any(keyword in gpu_lower for keyword in ['amd', 'radeon']):
                        self.recommended_tier = 3  # AMD -> Đi thẳng Lớp 3 (Ollama ROCm/Vulkan)
                    else:
                        self.recommended_tier = 3  # Card không xác định -> An toàn nhất là Lớp 3
                        
            except Exception:
                self.recommended_tier = 3  # Lỗi quét -> An toàn nhất là Lớp 3
                
        elif self.os_name == 'Darwin':
            # --- Mac: Apple Silicon (M1/M2/M3) hoặc Intel Mac ---
            self.vram_gb = self.total_ram_gb * 0.75  # Mac chia sẻ RAM cho GPU
            try:
                result = subprocess.run(
                    ['sysctl', '-n', 'machdep.cpu.brand_string'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                if result.returncode == 0:
                    cpu_brand = result.stdout.strip()
                    if 'Apple' in cpu_brand:
                        self.gpu_name = f"Apple Silicon ({platform.machine()})"
                        self.recommended_tier = 2  # Apple Metal -> Lớp 2 chạy cực mượt
                    else:
                        self.gpu_name = f"Intel Mac ({cpu_brand})"
                        self.recommended_tier = 3  # Intel Mac cũ -> Lớp 3 an toàn hơn
            except Exception:
                self.gpu_name = "Mac (Unknown)"
                self.recommended_tier = 2  # Mặc định Mac thử Lớp 2

    def _auto_select_llm(self):
        """Tự động chọn LLM Model dựa trên VRAM/RAM. Không cần hỏi người dùng."""
        models_map = {
            "14b": {"repo": "Qwen/Qwen2.5-14B-Instruct-GGUF", "file": "qwen2.5-14b-instruct-q4_k_m.gguf", "tag": "qwen2.5:14b", "label": "Qwen 2.5 (14B)", "disk_gb": 9.0},
            "7b":  {"repo": "Qwen/Qwen2.5-7B-Instruct-GGUF",  "file": "qwen2.5-7b-instruct-q4_k_m.gguf",  "tag": "qwen2.5:7b", "label": "Qwen 2.5 (7B)",  "disk_gb": 4.5},
            "3b":  {"repo": "Qwen/Qwen2.5-3B-Instruct-GGUF",  "file": "qwen2.5-3b-instruct-q4_k_m.gguf",  "tag": "qwen2.5:3b", "label": "Qwen 2.5 (3B)",  "disk_gb": 2.0},
            "0.5b":{"repo": "Qwen/Qwen2.5-0.5B-Instruct-GGUF","file": "qwen2.5-0.5b-instruct-q4_k_m.gguf","tag": "qwen2.5:0.5b", "label": "Qwen 2.5 (0.5B)","disk_gb": 0.5},
        }
        
<<<<<<< HEAD
        # 3. Kích hoạt Pull Model
        print(f"\n[Lớp 3] Đang kiểm tra bộ não AI: \033[92m{model_tag}\033[0m")
        try:
            list_output = subprocess.run([ollama_exe, "list"], capture_output=True, text=True).stdout
            if model_tag not in list_output:
                print(f"[Lớp 3] Đang tải mô hình từ mạng về (Cần WiFi)...")
                subprocess.run([ollama_exe, "pull", model_tag], check=True)
            else:
                print(f"[Lớp 3] Đã có sẵn mô hình Offline, bỏ qua tải xuống!")
            print(f"[Lớp 3] Sẵn sàng phục vụ!")
        except Exception as e:
            print(f"[Lớp 3] Lỗi khởi tạo {model_tag}: {str(e)}")

    def auto_setup(self):
        config = self.get_recommended_config()
        print(f"--- Auto Hardware Profiler & Model Zoo (3-Layer Auto-Adaptation) ---")
        gpu_str = ", ".join(self.gpu_names) if self.gpu_names else "None"
        print(f"OS: {self.os_name} | RAM: {self.total_ram_gb:.1f} GB | GPUs: {gpu_str} (VRAM: {self.vram_gb:.1f} GB)")
        print(f"Assigned Tier: {config['tier_name']}")
        print(f"--------------------------------------------------------------------")
        
        # Thử Lớp 1 và Lớp 2
        # Nếu phát hiện GPU là AMD hoặc Intel (không phải Nvidia/Apple Silicon) trên Windows,
        # ta nên chuyển thẳng sang Lớp 3 (Ollama) vì Ollama hỗ trợ tăng tốc GPU AMD/Intel rất tốt (ROCm/Vulkan),
        # tránh phải cài đặt llama-cpp-python CPU chậm và dễ lỗi tập lệnh.
        has_amd_intel = any(any(brand in name.lower() for brand in ["amd", "radeon", "intel", "iris", "arc", "xe"]) for name in self.gpu_names)
        if has_amd_intel and not self.has_cuda and platform.system() == "Windows":
            print("\n[Điều phối viên] Phát hiện GPU AMD/Intel. Đang tự động chuyển hướng sang Lớp 3 (Ollama) để tối ưu hóa tăng tốc phần cứng...")
            layer_1_2_success = False
        else:
            layer_1_2_success = self.setup_layer_1_and_2()
        
        if layer_1_2_success:
            model_path = self.check_and_install_model(config['repo_id'], config['filename'])
            config['model_path'] = model_path
            
            # Kiểm thử xem CPU có chạy được Llama (Pre-compiled) không
            if model_path and self.test_llama_cpp(model_path):
                config['engine'] = 'llama-cpp-python'
                return config
            else:
                print("\n[Điều phối viên] Phát hiện phần cứng không tương thích với Lớp 1/2. Đang tự động chuyển hướng...")
        else:
            if not (has_amd_intel and not self.has_cuda and platform.system() == "Windows"):
                print("\n[Điều phối viên] Không thể cài đặt Lớp 1/2. Đang tự động chuyển hướng...")
 
        # Chuyển sang Lớp 3
        self.setup_ollama_portable(config['model_tag'])
        config['engine'] = 'ollama'
        return config
=======
        # Quyết định dựa trên VRAM khả dụng (trừ ~1GB cho hệ thống)
        effective_vram = self.vram_gb - 1.0
        
        if effective_vram >= 12 and self.free_disk_gb >= 10:
            choice = "14b"
        elif effective_vram >= 6 and self.free_disk_gb >= 5:
            choice = "7b"
        elif effective_vram >= 2 and self.free_disk_gb >= 3:
            choice = "3b"
        else:
            choice = "0.5b"
        
        selected = models_map[choice]
        print(f"  🧠 LLM: {selected['label']} (Tốn ~{selected['disk_gb']}GB ổ cứng)")
        return selected

    def _auto_select_embedding(self):
        """Tự động chọn Embedding Model dựa trên RAM."""
        if self.total_ram_gb > 8:
            model = "GreenNode/GreenNode-Embedding-Large-VN-Mixed-V1"
            print("  📚 Embedding: GreenNode Large (Siêu chính xác)")
        else:
            model = "keepitreal/vietnamese-sbert"
            print("  📚 Embedding: Vietnamese-sBERT (Nhẹ, nhanh)")
        return model

    def _auto_select_reranker(self):
        """Tự động chọn Reranker Model dựa trên RAM."""
        if self.total_ram_gb > 8:
            model = "BAAI/bge-reranker-v2-m3"
            print("  🔍 Reranker: BGE-Reranker-v2-m3 (Chuẩn xác)")
        else:
            model = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
            print("  🔍 Reranker: mMiniLMv2 (Nhẹ, nhanh)")
        return model

    def _auto_select_whisper(self):
        """Tự động chọn Whisper Model Size dựa trên RAM."""
        if self.total_ram_gb >= 16:
            size = "medium"
            print("  🎙️ Whisper: Medium (Chính xác cao)")
        elif self.total_ram_gb >= 8:
            size = "small"
            print("  🎙️ Whisper: Small (Cân bằng)")
        else:
            size = "base"
            print("  🎙️ Whisper: Base (Siêu nhẹ)")
        return size

    def _auto_select_vision(self):
        """Tự động chọn Vision Model dựa trên VRAM và RAM."""
        # Ước lượng VRAM trống
        effective_vram = self.vram_gb - 1.0
        
        if effective_vram >= 8.0 and self.total_ram_gb >= 16:
            model = "llama3.2-vision"
            print("  👁️ Vision: Llama 3.2 Vision 11B (Siêu nét, cực nặng)")
        elif effective_vram >= 4.0 and self.total_ram_gb >= 8:
            model = "llava"
            print("  👁️ Vision: LLaVA 7B (Chi tiết tốt)")
        else:
            model = "moondream"
            print("  👁️ Vision: Moondream 1.6B (Siêu tốc, siêu nhẹ)")
        return model

    def auto_setup(self):
        """Khởi tạo lần đầu hoàn toàn tự động. Không yêu cầu input từ người dùng."""
        print("\n" + "="*50)
        print("🤖 NOTEBOOKLM MINI - KHỞI TẠO TỰ ĐỘNG 🤖")
        print("="*50)
        print(f"📌 [Phân tích hệ thống]")
        print(f" - Hệ điều hành: {self.os_name}")
        print(f" - RAM vật lý: {self.total_ram_gb:.1f} GB")
        print(f" - Card đồ hoạ: {self.gpu_name}")
        print(f" - VRAM: {self.vram_gb:.1f} GB")
        print(f" - Ổ đĩa trống: {self.free_disk_gb:.1f} GB")
        
        # Hiển thị Lớp được chọn
        tier_labels = {
            2: "Lớp 2 (Native - CUDA/Metal)",
            3: "Lớp 3 (Ollama - Vulkan/ROCm/Auto)"
        }
        print(f" - 🎯 Lớp khuyến nghị: {tier_labels.get(self.recommended_tier, 'Lớp 3')}")
        print("="*50)
        
        # === TỰ ĐỘNG CHỌN TẤT CẢ MODEL ===
        print("\n⚙️ [Tự động lựa chọn bộ Model tối ưu cho cấu hình của bạn]")
        
        selected_model = self._auto_select_llm()
        embedding_model = self._auto_select_embedding()
        reranker_model = self._auto_select_reranker()
        whisper_size = self._auto_select_whisper()
        vision_model = self._auto_select_vision()

        # Ghi cấu hình vào .env
        self._write_env_config(embedding_model, reranker_model, whisper_size, vision_model)

        print("\n⏳ Đang tiến hành thiết lập hệ thống tự động...")
        
        # 1. Sinh file requirements.txt
        self._generate_requirements()
            
        # 2. Cơ chế Fallback 3 Lớp: Cài đặt AI Engine
        llama = LlamaManager()
        engine_installed = None
        server_exe = None
        model_path = None
        
        if self.recommended_tier == 2:
            print("\n⏳ [Điều phối viên] Thử nghiệm Lớp 1 (Tự động biên dịch từ mã nguồn)...")
            if llama.setup_layer_1():
                model_path = llama.download_model(selected_model["repo"], selected_model["file"])
                if llama.test_llama_cpp(model_path):
                    engine_installed = "llama-cpp-python"
                    print("\n✅ Lớp 1 cài đặt thành công!")
                else:
                    print("\n⚠️ Lớp 1 thất bại (Xung đột AVX). Chuyển sang Lớp 2...")
            
            if engine_installed is None:
                print("\n⏳ [Điều phối viên] Đang cài đặt Lớp 2 (llama-server Native)...")
                server_exe = llama.setup_llama_server(has_cuda=False, has_vulkan=self.has_cuda)
                model_path = llama.download_model(selected_model["repo"], selected_model["file"])
                engine_installed = "llama-server"
                print("\n✅ Lớp 2 cài đặt thành công!")
        else:
            print("\n⏳ [Điều phối viên] Hệ thống yêu cầu sử dụng Lớp 3 (Ollama)...")
            if llama.setup_ollama():
                engine_installed = "ollama"
                model_path = selected_model["tag"]
                print("\n✅ Lớp 3 (Ollama) đã được cài đặt và kích hoạt!")
            else:
                print("\n❌ Cài đặt Ollama thất bại!")
        
        print("\n✅ Đã tạo cấu hình và thiết lập AI engine hoàn tất!")
        
        return {
            "engine_installed": engine_installed,
            "server_exe": server_exe,
            "model_path": model_path,
            "has_cuda": self.has_cuda,
            "has_mac_gpu": self.os_name == 'Darwin',
            "recommended_tier": self.recommended_tier,
            "gpu_name": self.gpu_name,
            "selected_llm": selected_model,
            "whisper_size": whisper_size,
        }

    def _write_env_config(self, embedding_model, reranker_model, whisper_size, vision_model):
        """Ghi cấu hình model đã chọn vào file .env."""
        import re
        env_path = os.path.join(os.getcwd(), ".env")
        env_content = ""
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                env_content = f.read()
        
        # Cập nhật hoặc thêm các biến cấu hình
        config_updates = {
            "RAG_EMBEDDING_MODEL": embedding_model,
            "RAG_RERANKER_MODEL": reranker_model,
            "RAG_VISION_MODE": "ollama",
            "RAG_VISION_MODEL": vision_model,
            "RAG_AUDIO_MODEL": whisper_size,
        }
        
        for key, value in config_updates.items():
            if key in env_content:
                env_content = re.sub(rf'{key}=.*', f'{key}={value}', env_content)
            else:
                env_content += f"\n{key}={value}\n"
        
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(env_content)

    def _generate_requirements(self):
        """Sinh file requirements.txt với PyTorch phù hợp phần cứng."""
        req_base_path = os.path.join(os.getcwd(), "requirements-base.txt")
        req_out_path = os.path.join(os.getcwd(), "requirements.txt")
        
        with open(req_base_path, "r", encoding="utf-8") as f:
            req_content = f.read()
        
        # Chốt cứng llvmlite để tránh lỗi trên Python 3.13.1
        if "llvmlite" not in req_content:
            req_content += "\n# Fix: Chốt phiên bản llvmlite cho Python 3.13+\nllvmlite>=0.43.0\n"
            
        pytorch_mode = "gpu" if self.has_cuda else "cpu"
        
        if pytorch_mode == "cpu":
            if self.os_name == "Darwin":
                print("📦 PyTorch: Apple Metal (Native)")
                req_content += "\n# --- PyTorch Apple Metal ---\n"
                req_content += "torch>=2.0.0\n"
            else:
                print("📦 PyTorch: CPU-Only (Diet Plan)")
                req_content += "\n# --- PyTorch CPU-Only (Diet Plan) ---\n"
                req_content += "--extra-index-url https://download.pytorch.org/whl/cpu\n"
                req_content += "torch==2.6.0+cpu\n"
                req_content += "torchvision==0.21.0+cpu\n"
                req_content += "torchaudio==2.6.0+cpu\n"
        else:
            print("📦 PyTorch: Full Speed (NVIDIA GPU)")
            req_content += "\n# --- PyTorch Full Speed ---\n"
            req_content += "torch>=2.0.0\n"
            
        with open(req_out_path, "w", encoding="utf-8") as f:
            f.write(req_content)
>>>>>>> f9596404713f72a50f34b3f444ecafca4bfa705c

if __name__ == "__main__":
    manager = ModelZooManager()
    manager.auto_setup()
