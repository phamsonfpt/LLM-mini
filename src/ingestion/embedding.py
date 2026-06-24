from typing import List
from sentence_transformers import SentenceTransformer
from ..utils.config import settings

class LocalEmbedder:
    """Quản lý Embedding Model với khả năng tự động chọn Device theo Hardware Profiler."""
    
    def __init__(self, model_name: str = None):
        # Ưu tiên lấy model từ tham số, nếu không thì lấy mặc định (ví dụ BAAI/bge-m3)
        self.model_name = model_name or "BAAI/bge-m3"
        self.device = settings.hf_device if settings.hf_device != "auto" else None
        
        print(f"[LocalEmbedder] Đang tải mô hình {self.model_name} lên thiết bị: {self.device}", flush=True)
        
        # Load model using sentence-transformers (try offline first to avoid network check hangs)
        import os
        import socket

        def is_online() -> bool:
            try:
                socket.setdefaulttimeout(2)
                # Thử phân giải DNS tên miền chính trước
                socket.gethostbyname("huggingface.co")
                return True
            except Exception:
                try:
                    # Dự phòng kết nối trực tiếp IP của DNS
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect(("8.8.8.8", 53))
                    s.close()
                    return True
                except Exception:
                    return False

        online_status = is_online()
        if not online_status:
            print("[LocalEmbedder] Phát hiện trạng thái ngoại tuyến (Offline). Ép buộc sử dụng local cache...")
            os.environ["HF_HUB_OFFLINE"] = "1"
            os.environ["TRANSFORMERS_OFFLINE"] = "1"

        try:
            self.model = SentenceTransformer(self.model_name, device=self.device, local_files_only=True)
        except Exception as e:
            if not online_status:
                raise RuntimeError(
                    f"Không thể tải mô hình Embedding '{self.model_name}' ở chế độ ngoại tuyến (Offline).\n"
                    f"Nguyên nhân: Mô hình chưa được tải về máy trước đó.\n"
                    f"Cách khắc phục: Vui lòng bật kết nối mạng Internet (WiFi) để chạy hệ thống lần đầu, "
                    f"sau khi tải xong mô hình bạn có thể tắt WiFi và sử dụng offline bình thường."
                ) from e
            print(f"[LocalEmbedder] Tải offline thất bại, đang thử tải qua Internet: {e}", flush=True)
            self.model = SentenceTransformer(self.model_name, device=self.device)
        
        # Nếu thiết bị là CPU và config cấu hình là int8_onnx, 
        # (Lưu ý: sentence-transformers không hỗ trợ export onnx trực tiếp dễ dàng,
        # Trong hệ thống thực tế, ta có thể dùng thư viện optimum để tải bản ONNX.
        # Ở đây ta sử dụng cấu hình CPU native của PyTorch đã được tối ưu hóa).
        if getattr(settings, "embedding_quantization", None) == "int8_onnx" and self.device == "cpu":
            print("[LocalEmbedder] Đang tối ưu hóa chạy CPU cho môi trường Tier 3/4...")

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Nhúng danh sách các đoạn văn bản (Dùng cho Ingestion) với Micro-Batching."""
        if not texts:
            return []
            
        # Giải phóng bộ nhớ đệm của MPS/CUDA trước khi chạy nếu có thể
        try:
            import torch
            if hasattr(torch, "mps") and torch.mps.is_available():
                torch.mps.empty_cache()
            elif torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

        # Dùng batch_size = 4 để tránh tràn bộ nhớ GPU/MPS (OOM) trên các máy Mac 8GB RAM
        batch_size = 4
        all_embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i+batch_size]
            current_batch = (i // batch_size) + 1
            print(f"[LocalEmbedder] Đang nhúng gói {current_batch}/{total_batches} ({len(batch_texts)} mục)...", flush=True)
            
            try:
                batch_embeddings = self.model.encode(batch_texts, convert_to_numpy=True, show_progress_bar=False)
            except RuntimeError as e:
                # Nếu tràn bộ nhớ GPU/MPS, tự động chuyển sang CPU
                if "out of memory" in str(e).lower() or "mps" in str(e).lower() or "cuda" in str(e).lower():
                    print(f"[LocalEmbedder] Cảnh báo: Tràn bộ nhớ GPU ({e}). Tự động fallback sang tính toán trên CPU...", flush=True)
                    try:
                        self.model.to("cpu")
                        self.device = "cpu"
                    except Exception:
                        pass
                    batch_embeddings = self.model.encode(batch_texts, convert_to_numpy=True, show_progress_bar=False)
                else:
                    raise e
            all_embeddings.extend(batch_embeddings.tolist())
            
        return all_embeddings

    def embed_query(self, text: str) -> List[float]:
        """Nhúng một câu truy vấn duy nhất (Dùng cho Retrieval)."""
        try:
            import torch
            if hasattr(torch, "mps") and torch.mps.is_available():
                torch.mps.empty_cache()
        except Exception:
            pass

        try:
            embedding = self.model.encode(text, convert_to_numpy=True, show_progress_bar=False)
        except RuntimeError as e:
            if "out of memory" in str(e).lower() or "mps" in str(e).lower() or "cuda" in str(e).lower():
                print(f"[LocalEmbedder] Cảnh báo: Tràn bộ nhớ GPU ({e}). Tự động fallback sang tính toán trên CPU...", flush=True)
                try:
                    self.model.to("cpu")
                    self.device = "cpu"
                except Exception:
                    pass
                embedding = self.model.encode(text, convert_to_numpy=True, show_progress_bar=False)
            else:
                raise e
        return embedding.tolist()
