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
        """Hàm chạy ngầm để sinh và lưu Study Guide."""
        logger.info(f"Bắt đầu sinh Study Guide cho Notebook {notebook_id}...")
        
        # Giới hạn text (ví dụ 10,000 ký tự đầu tiên) để tránh vượt quá context window
        context = document_text[:10000]

        try:
            # 1. Sinh Tóm tắt (Summary)
            summary_prompt = f"Dựa vào tài liệu sau, hãy viết một bản tóm tắt ngắn gọn (Executive Summary) bằng tiếng Việt:\n\n{context}"
            summary = "".join(self.llm.generate(summary_prompt, system_prompt="Bạn là chuyên gia phân tích tài liệu.", is_private=is_private, gemini_api_key=gemini_api_key))
            logger.info("Đã sinh xong Summary.")

            # 2. Sinh FAQ
            faq_prompt = f"Dựa vào tài liệu sau, hãy tạo ra 3-5 câu hỏi thường gặp (FAQ) và câu trả lời tương ứng bằng tiếng Việt. Định dạng rõ ràng Hỏi và Đáp:\n\n{context}"
            faq = "".join(self.llm.generate(faq_prompt, system_prompt="Bạn là chuyên gia thiết kế bài giảng.", is_private=is_private, gemini_api_key=gemini_api_key))
            logger.info("Đã sinh xong FAQ.")

            # 3. Sinh Glossary (Thuật ngữ)
            glossary_prompt = f"Dựa vào tài liệu sau, hãy trích xuất 5 thuật ngữ quan trọng nhất và giải thích chúng bằng tiếng Việt:\n\n{context}"
            glossary = "".join(self.llm.generate(glossary_prompt, system_prompt="Bạn là từ điển sống chuyên ngành.", is_private=is_private, gemini_api_key=gemini_api_key))
            logger.info("Đã sinh xong Glossary.")

            # 4. Sinh Quiz
            quiz_prompt = (
                f"Dựa vào tài liệu sau, hãy tạo ra 5 câu hỏi trắc nghiệm tiếng Việt. "
                f"Định dạng trả về là chuỗi JSON array, KHÔNG CÓ MARKDOWN HAY BẤT KỲ VĂN BẢN NÀO KHÁC BÊN NGOÀI. "
                f"Mỗi phần tử có dạng: {{\"question\": \"Câu hỏi\", \"options\": [\"A\", \"B\", \"C\", \"D\"], \"answer\": 0}}\n\n"
                f"Tài liệu:\n{context}"
            )
            quiz_json = "".join(self.llm.generate(quiz_prompt, system_prompt="Bạn là giáo viên ra đề thi trắc nghiệm. CHỈ TRẢ VỀ JSON, không trả về markdown block (không chứa ```json).", is_private=is_private, gemini_api_key=gemini_api_key))
            quiz_json = quiz_json.strip()
            if quiz_json.startswith("```json"):
                quiz_json = quiz_json.replace("```json", "", 1).strip()
            if quiz_json.endswith("```"):
                quiz_json = quiz_json[::-1].replace("```", "", 1)[::-1].strip()
            logger.info("Đã sinh xong Quiz.")

            # 5. Sinh Flashcards
            flashcard_prompt = (
                f"Dựa vào tài liệu sau, hãy tạo ra 5 thẻ từ vựng (flashcard) tiếng Việt. "
                f"Định dạng trả về là chuỗi JSON array, KHÔNG CÓ MARKDOWN HAY BẤT KỲ VĂN BẢN NÀO KHÁC BÊN NGOÀI. "
                f"Mỗi phần tử có dạng: {{\"front\": \"Mặt trước (Khái niệm/Câu hỏi)\", \"back\": \"Mặt sau (Định nghĩa/Câu trả lời)\"}}\n\n"
                f"Tài liệu:\n{context}"
            )
            flashcards_json = "".join(self.llm.generate(flashcard_prompt, system_prompt="Bạn là giáo viên tạo thẻ nhớ. CHỈ TRẢ VỀ JSON, không trả về markdown block (không chứa ```json).", is_private=is_private, gemini_api_key=gemini_api_key))
            flashcards_json = flashcards_json.strip()
            if flashcards_json.startswith("```json"):
                flashcards_json = flashcards_json.replace("```json", "", 1).strip()
            if flashcards_json.endswith("```"):
                flashcards_json = flashcards_json[::-1].replace("```", "", 1)[::-1].strip()
            logger.info("Đã sinh xong Flashcards.")

            # Lưu vào Database
            self.db.save_study_guide(notebook_id, summary, faq, glossary, quiz=quiz_json, flashcards=flashcards_json)
            logger.info(f"Hoàn thành sinh Study Guide cho {notebook_id}.")
        except Exception as e:
            logger.error(f"Lỗi khi sinh Study Guide: {e}")
            error_msg = f"Đã có lỗi xảy ra khi tạo Cẩm nang học tập: {str(e)}"
            self.db.save_study_guide(notebook_id, error_msg, error_msg, error_msg, quiz=None, flashcards=None)

