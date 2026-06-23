import os
import json
import requests
import logging
from typing import Generator, Optional
import threading

logger = logging.getLogger(__name__)

class LLMEngine:
    """
    LLM Engine sử dụng Cơ chế Auto-Adaptation 3 Lớp.
    Tự động chuyển đổi giữa llama-cpp-python và Ollama Portable.
    """
    def __init__(self):
        from src.utils.hardware_profiler import ModelZooManager
        
        logger.info("Đang kiểm tra và tải cấu hình LLM phù hợp với máy tính...")
        manager = ModelZooManager()
        self.config = manager.auto_setup()
        
        self.engine = self.config.get('engine', 'ollama')
        self.model_tag = self.config.get('model_tag')
        self.model_path = self.config.get('model_path')
        self.tier = manager.get_tier()
        self.lock = threading.Lock()
        
        self.llm = None
        if self.engine == 'llama-cpp-python':
            # Khởi tạo Llama-cpp (đã test thành công ở Lớp 1/2)
            n_gpu_layers = -1 if (self.tier in [1, 2, 3] or manager.has_mps or manager.has_cuda) else 0
            n_ctx = 8192 # Tăng lên 8192 để chứa RAG context dài
            
            # Tối ưu hóa số luồng CPU bằng số nhân vật lý (tránh nghẽn hyper-threading)
            import psutil
            n_threads = psutil.cpu_count(logical=False) or 4
            logger.info(f"Khởi tạo Llama-cpp với {n_threads} CPU threads (nhân vật lý).")
            
            from llama_cpp import Llama
            try:
                self.llm = Llama(
                    model_path=self.model_path,
                    n_gpu_layers=n_gpu_layers,
                    n_ctx=n_ctx,
                    n_threads=n_threads,
                    verbose=False
                )
            except Exception as e:
                logger.error(f"Lỗi khởi tạo Llama: {e}")
                self.engine = 'ollama' # Fallback nếu đột ngột lỗi

    def generate(self, prompt: str, system_prompt: str = "", is_private: bool = True, gemini_api_key: Optional[str] = None) -> Generator[str, None, None]:
        """Tạo phản hồi dạng Stream (nhả từng chữ)."""
        if not is_private and gemini_api_key:
            from google import genai
            from google.genai import types
            try:
                client = genai.Client(api_key=gemini_api_key)
                response = client.models.generate_content_stream(
                    model='gemini-2.5-flash',
                    contents=[
                        types.Content(role="user", parts=[types.Part.from_text(text=system_prompt + "\n\n" + prompt)])
                    ]
                )
                for chunk in response:
                    yield chunk.text
                return
            except Exception as e:
                logger.error(f"Lỗi Gemini API: {e}")
                yield f"Lỗi Gemini API: {e}. Đang fallback về Local Model..."
        
        if self.engine == 'llama-cpp-python' and getattr(self, 'llm', None):
            # Dùng Lớp 1/2: Llama-cpp-python
            # Kết hợp Queue + Background Thread để vừa giữ được typewriter real-time streaming (UX),
            # vừa giải phóng Lock ngay khi AI vừa chạy xong (không bị treo Lock do mạng client chậm - Bug 3)
            import queue
            import threading
            
            token_queue = queue.Queue()
            
            def generate_tokens_worker():
                try:
                    with self.lock:
                        stream = self.llm.create_chat_completion(
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt}
                            ],
                            max_tokens=1024, # Trả lời dài nhất 1024 tokens (tiết kiệm không gian context cho câu hỏi)
                            temperature=0.2, # Giảm nhiệt độ để bám sát fact, tránh bịa đặt
                            repeat_penalty=1.15, # Phạt lặp từ (rất quan trọng cho model 1B/3B)
                            top_p=0.9,
                            stream=True
                        )
                        for chunk in stream:
                            if 'choices' in chunk and len(chunk['choices']) > 0:
                                delta = chunk['choices'][0].get('delta', {})
                                if 'content' in delta:
                                    token_queue.put(delta['content'])
                except Exception as e:
                    logger.error(f"Lỗi trong luồng sinh chữ Llama-cpp: {e}")
                    token_queue.put(f"[Lỗi sinh chữ: {e}]")
                finally:
                    token_queue.put(None)  # Sentinel báo kết thúc
            
            try:
                # Khởi chạy luồng sinh chữ ngầm
                t = threading.Thread(target=generate_tokens_worker)
                t.daemon = True
                t.start()
                
                # Trả dần kết quả (yield) ra client ngay khi có chữ
                while True:
                    token = token_queue.get()
                    if token is None:
                        break
                    yield token
                return
            except Exception as e:
                logger.error(f"Lỗi gọi Llama-cpp: {e}")
                yield f"Đã có lỗi xảy ra từ Llama-cpp: {e}"
                return
                
        # Dùng Lớp 3: Gọi Ollama REST API
        try:
            payload = {
                "model": self.model_tag,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "stream": True
            }
            
            with requests.post("http://127.0.0.1:11434/api/chat", json=payload, stream=True) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line:
                        chunk_data = json.loads(line)
                        if "message" in chunk_data and "content" in chunk_data["message"]:
                            yield chunk_data["message"]["content"]
                            
        except requests.exceptions.ConnectionError:
            error_msg = (
                "⚠️ **Lỗi hệ thống: Không thể kết nối tới Ollama!**\n\n"
                "Sổ tay này đang ở chế độ **Nội bộ (Offline)**. Hệ thống AI đang được khởi động ngầm, vui lòng chờ vài giây rồi thử lại.\n"
                "Nếu lỗi vẫn tiếp diễn, máy tính của bạn có thể đã chặn cổng 11434."
            )
            logger.error("Không thể kết nối Ollama.")
            yield error_msg
            
        except Exception as e:
            logger.error(f"Lỗi không xác định khi gọi Local LLM: {e}")
            yield "Đã có lỗi xảy ra trong quá trình sinh văn bản từ AI nội bộ."

    def build_rag_prompt(self, query: str, context: str) -> str:
        """Tạo Prompt hoàn chỉnh cho RAG."""
        return (
            f"Bạn là trợ lý AI chuyên nghiệp tên là NotebookLM Mini. Dưới đây là các thông tin tôi tìm thấy trong tài liệu của bạn:\n"
            f"====================\n{context}\n====================\n\n"
            f"YÊU CẦU QUAN TRỌNG VỀ PHONG CÁCH TRẢ LỜI:\n"
            f"1. Hãy tổng hợp (synthesis) thông tin một cách mạch lạc và tự nhiên. Tuyệt đối không liệt kê máy móc từng nguồn (ví dụ tránh viết: 'Nguồn 1: ..., Nguồn 2: ...' hoặc 'Nguồn 1 nói về A, Nguồn 2 nói về B...').\n"
            f"2. Trình bày câu trả lời dưới dạng một văn bản thống nhất, trôi chảy. Chỉ chú thích nguồn bằng các ký hiệu như [1], [2] hoặc [Tổng quan] ở cuối câu tương ứng.\n"
            f"3. Dựa vào thông tin cung cấp ở trên, hãy trả lời câu hỏi sau một cách chi tiết và chính xác nhất. Nếu tài liệu không có thông tin, hãy nói rõ là tài liệu không đề cập.\n\n"
            f"Câu hỏi: {query}"
        )