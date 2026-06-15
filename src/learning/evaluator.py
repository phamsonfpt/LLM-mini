import logging
from typing import Dict, Any
from ..llm.llm_client import LLMEngine
from ..db.session_manager import SessionManager

logger = logging.getLogger(__name__)

class Evaluator:
    """Tự động đánh giá kiến thức của người dùng dựa trên lịch sử hội thoại."""
    def __init__(self, llm_engine: LLMEngine, session_manager: SessionManager):
        self.llm = llm_engine
        self.db = session_manager

    def evaluate_knowledge(self, notebook_id: str, is_private: bool = True, gemini_api_key: str = None) -> Dict[str, Any]:
        """Đánh giá trình độ hiểu biết dựa trên lịch sử hỏi đáp và tài liệu liên quan."""
        logger.info(f"Đang tiến hành đánh giá Notebook {notebook_id}...")
        
        history = self.db.get_chat_history(notebook_id)
        if not history or len(history) < 2:
            return {
                "score": 0,
                "feedback": "Hệ thống chưa đủ dữ liệu hội thoại để đánh giá. Vui lòng đặt thêm câu hỏi liên quan đến tài liệu.",
                "strengths": [],
                "weaknesses": []
            }
            
        guide = self.db.get_study_guide(notebook_id)
        summary = guide.get("summary", "") if guide else ""
        
        user_queries = [msg["content"] for msg in history if msg["role"] == "user"]
        queries_text = "\n- ".join(user_queries)
        
        prompt = (
            f"Dưới đây là nội dung cốt lõi của tài liệu:\n{summary}\n\n"
            f"Dưới đây là danh sách các câu hỏi mà người dùng đã đặt:\n- {queries_text}\n\n"
            f"Hãy đánh giá tổng quan trình độ nắm bắt kiến thức của người dùng dựa trên mức độ sâu sắc, "
            f"tính logic và trọng tâm của các câu hỏi. Định dạng trả về phải là chuỗi JSON với cấu trúc "
            f"chính xác như sau, KHÔNG THÊM BẤT KỲ VĂN BẢN NÀO KHÁC:\n"
            f"{{\n"
            f"  \"score\": 8,\n"
            f"  \"feedback\": \"<Đánh giá tổng quan (tiếng Việt)>\",\n"
            f"  \"strengths\": [\"<điểm mạnh 1>\", \"<điểm mạnh 2>\"],\n"
            f"  \"weaknesses\": [\"<điểm yếu 1>\", \"<điểm yếu 2>\"]\n"
            f"}}"
        )
        
        raw_json = "".join(self.llm.generate(prompt, system_prompt="Bạn là giám khảo chuyên môn chấm điểm mức độ hiểu biết. Chỉ trả về JSON.", is_private=is_private, gemini_api_key=gemini_api_key))
        raw_json = raw_json.strip()
        if raw_json.startswith("```json"):
            raw_json = raw_json.replace("```json", "", 1).strip()
        if raw_json.endswith("```"):
            raw_json = raw_json[::-1].replace("```", "", 1)[::-1].strip()
            
        import json
        try:
            metrics = json.loads(raw_json)
            return metrics
        except Exception as e:
            logger.error(f"Lỗi parse JSON đánh giá: {e}")
            return {
                "score": 5,
                "feedback": "Có lỗi xảy ra khi tổng hợp kết quả đánh giá.",
                "strengths": ["N/A"],
                "weaknesses": ["N/A"]
            }
