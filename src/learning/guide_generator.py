import json
import logging
from ..llm.llm_client import LLMEngine
from ..db.session_manager import SessionManager

logger = logging.getLogger(__name__)

class GuideGenerator:
    """Tự động sinh Study Guide (Cẩm nang học tập) từ tài liệu."""
    def __init__(self, llm_engine: LLMEngine, session_manager: SessionManager):
        self.llm = llm_engine
        self.db = session_manager

    def generate(self, notebook_id: str, document_text: str, is_private: bool = True, gemini_api_key: str = None):
        """
        Hàm tự động sinh chung (generate) đã bị loại bỏ vì tính năng Cẩm nang học tập hiện tại
        yêu cầu người dùng chủ động sinh từng phần (Quiz, Flashcard, Mindmap, Podcast) để tiết kiệm tài nguyên.
        Lưu ý: Tóm tắt (Summary) có thể hỏi trực tiếp qua Chat.
        """
        pass

    def generate_custom_quiz(self, notebook_id: str, context: str, topic: str, difficulty: str, amount: int, language: str, is_private: bool = True, gemini_api_key: str = None) -> str:
        """Sinh quiz tùy chỉnh theo yêu cầu."""
        prompt = (
            f"Dựa vào tài liệu sau, hãy tạo ra {amount} câu hỏi trắc nghiệm bằng ngôn ngữ '{language}'.\n"
            f"Chủ đề tập trung: {topic}\n"
            f"Độ khó: {difficulty}\n"
            f"Định dạng trả về là chuỗi JSON array, KHÔNG CÓ MARKDOWN HAY BẤT KỲ VĂN BẢN NÀO KHÁC BÊN NGOÀI. "
            f"Mỗi phần tử có dạng: {{\"question\": \"Câu hỏi\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"answer\": 0}}\n\n"
            f"Tài liệu:\n{context[:15000]}"
        )
        quiz_json = "".join(self.llm.generate(prompt, system_prompt="Bạn là chuyên gia giáo dục. CHỈ TRẢ VỀ JSON hợp lệ.", is_private=is_private, gemini_api_key=gemini_api_key)).strip()
        if quiz_json.startswith("```json"): quiz_json = quiz_json.replace("```json", "", 1).strip()
        if quiz_json.endswith("```"): quiz_json = quiz_json[::-1].replace("```", "", 1)[::-1].strip()
        return quiz_json

    def generate_custom_flashcards(self, notebook_id: str, context: str, topic: str, difficulty: str, amount: int, language: str, is_private: bool = True, gemini_api_key: str = None) -> str:
        """Sinh flashcard tùy chỉnh theo yêu cầu."""
        prompt = (
            f"Dựa vào tài liệu sau, hãy tạo ra {amount} thẻ từ vựng (flashcard) bằng ngôn ngữ '{language}'.\n"
            f"Chủ đề tập trung: {topic}\n"
            f"Độ khó: {difficulty}\n"
            f"Định dạng trả về là chuỗi JSON array, KHÔNG CÓ MARKDOWN HAY BẤT KỲ VĂN BẢN NÀO KHÁC BÊN NGOÀI. "
            f"Mỗi phần tử có dạng: {{\"front\": \"Mặt trước (Khái niệm/Câu hỏi ngắn)\", \"back\": \"Mặt sau (Định nghĩa/Giải thích)\"}}\n\n"
            f"Tài liệu:\n{context[:15000]}"
        )
        flashcards_json = "".join(self.llm.generate(prompt, system_prompt="Bạn là giáo viên. CHỈ TRẢ VỀ JSON hợp lệ.", is_private=is_private, gemini_api_key=gemini_api_key)).strip()
        if flashcards_json.startswith("```json"): flashcards_json = flashcards_json.replace("```json", "", 1).strip()
        if flashcards_json.endswith("```"): flashcards_json = flashcards_json[::-1].replace("```", "", 1)[::-1].strip()
        return flashcards_json

    def generate_custom_mindmap(self, notebook_id: str, context: str, topic: str, is_private: bool = True, gemini_api_key: str = None) -> str:
        """Sinh mindmap tùy chỉnh dưới định dạng Markdown."""
        prompt = (
            f"Dựa vào tài liệu sau, hãy tạo ra một bản đồ tư duy dưới dạng danh sách Markdown (Markdown list) nhiều cấp độ để thể hiện cấu trúc thông tin.\n"
            f"Chủ đề tập trung: {topic}\n"
            f"Sử dụng các dấu đầu dòng (- hoặc *) và thụt lề để thể hiện cấu trúc phân cấp (ví dụ: Ý chính -> Ý phụ -> Chi tiết).\n\n"
            f"Tài liệu:\n{context[:15000]}"
        )
        mindmap_md = "".join(self.llm.generate(prompt, system_prompt="Bạn là chuyên gia tổng hợp thông tin. Chỉ trả về Markdown list.", is_private=is_private, gemini_api_key=gemini_api_key)).strip()
        return mindmap_md

