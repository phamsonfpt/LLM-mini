import os
from typing import Generator
from llama_cpp import Llama
from ..utils.config import settings
from ..utils.hardware_profiler import ModelZooManager

class LLMEngine:
    """Động cơ sinh văn bản (LLM Engine) chạy nội bộ bằng llama.cpp."""
    
    def __init__(self):
        # Lấy model được hardware_profiler đề xuất
        manager = ModelZooManager()
        self.tier = manager.get_tier()
        
        # Nếu đã tải model qua ollama (trong kịch bản profiler), 
        # Thực ra llama-cpp-python yêu cầu file .gguf cục bộ. 
        # Trong thiết kế Local RAG chuẩn 1-click không cần Docker/Ollama chạy ngầm,
        # Ta nên tải trực tiếp file GGUF từ HuggingFace về thư mục models/.
        # Để demo, giả sử file .gguf đã có sẵn ở settings.model_path.
        self.model_path = getattr(settings, "model_path", "models/llm_model.gguf")
        
        # Cấu hình VRAM tùy Tier
        n_gpu_layers = -1 if self.tier in [1, 2] else 0
        n_ctx = 4096
        
        print(f"[LLMEngine] Đang nạp LLM (Tier {self.tier}) với {n_gpu_layers} GPU layers...")
        
        # Khởi tạo Llama
        if os.path.exists(self.model_path):
            self.llm = Llama(
                model_path=self.model_path,
                n_gpu_layers=n_gpu_layers,
                n_ctx=n_ctx,
                verbose=False
            )
        else:
            print(f"[LLMEngine] ⚠️ Không tìm thấy file model tại {self.model_path}. Chế độ Mock LLM được bật.")
            self.llm = None

    def generate(self, prompt: str, system_prompt: str = "") -> Generator[str, None, None]:
        """Tạo phản hồi dạng Stream (nhả từng chữ)."""
        if not self.llm:
            yield "Hệ thống chưa tải được Model AI (Chế độ giả lập). Câu trả lời của bạn ở đây."
            return
            
        formatted_prompt = f"System: {system_prompt}\nUser: {prompt}\nAssistant:"
        
        stream = self.llm(
            formatted_prompt,
            max_tokens=1024,
            stop=["User:", "\nSystem:"],
            stream=True
        )
        
        for output in stream:
            chunk = output['choices'][0]['text']
            yield chunk

    def build_rag_prompt(self, query: str, context: str) -> str:
        """Tạo Prompt hoàn chỉnh cho RAG."""
        return (
            f"Dưới đây là các thông tin tôi tìm thấy trong tài liệu của bạn:\n"
            f"...\n{context}\n...\n\n"
            f"Dựa vào thông tin trên, hãy trả lời câu hỏi sau một cách chi tiết và chính xác nhất.\n"
            f"Câu hỏi: {query}"
        )
