import logging
from jinja2 import Environment, FileSystemLoader
from ..llm.llm_client import LLMEngine

logger = logging.getLogger(__name__)

class QueryRewriter:
    """Tái cấu trúc câu hỏi (Sửa lỗi chính tả, mở rộng từ khóa) trước khi tìm kiếm."""
    
    def __init__(self):
        # Sử dụng LLMEngine hiện tại (Llama/Qwen)
        self.llm = LLMEngine()
        self.env = Environment(loader=FileSystemLoader("src/prompts"))
        self.template = self.env.get_template("query_rewrite.jinja2")
        
    def rewrite(self, query: str) -> str:
        """Sửa lỗi chính tả và làm rõ câu hỏi."""
        # Nếu câu hỏi quá ngắn (ví dụ: chỉ 1 chữ) thì không cần rewrite
        if len(query.strip().split()) < 2:
            return query
            
        try:
            prompt = self.template.render(query=query)
            # Gọi LLM sinh text không stream
            logger.info(f"Đang phân tích câu hỏi: '{query}'")
            rewritten_query = "".join(self.llm.generate(prompt, system_prompt="Bạn là máy tính sửa lỗi chính tả, chỉ xuất ra câu đã sửa.")).strip()
            
            # Xóa ngoặc kép nếu AI vô tình thêm vào
            rewritten_query = rewritten_query.strip('"').strip("'")
            
            if rewritten_query and rewritten_query.lower() != query.lower():
                logger.info(f"Đã sửa chính tả: '{query}' -> '{rewritten_query}'")
                return rewritten_query
                
            return query
            
        except Exception as e:
            logger.error(f"Lỗi khi rewrite query: {e}")
            return query
