import os
import logging
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    context_precision,
    answer_relevancy,
    faithfulness,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

class RagasEvaluator:
    """Đánh giá RAG sử dụng Ragas."""
    
    def __init__(self):
        # Yêu cầu GOOGLE_API_KEY
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.warning("Không tìm thấy GOOGLE_API_KEY. Ragas có thể không hoạt động.")
            
        self.llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", google_api_key=api_key)
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=api_key)
        
    def evaluate_batch(self, questions: list[str], answers: list[str], contexts: list[list[str]], ground_truths: list[str] = None):
        """
        Chấm điểm một loạt các câu hỏi.
        questions: danh sách câu hỏi của user
        answers: danh sách câu trả lời của AI
        contexts: danh sách list các đoạn văn bản truy xuất được
        ground_truths: câu trả lời mẫu (có thể bỏ qua)
        """
        data = {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
        }
        
        if ground_truths:
            data["ground_truth"] = ground_truths
            
        dataset = Dataset.from_dict(data)
        
        # Chọn metrics
        metrics = [
            context_precision,
            answer_relevancy,
            faithfulness,
        ]
        
        logger.info(f"Đang bắt đầu chấm điểm {len(questions)} câu trả lời bằng Ragas...")
        try:
            result = evaluate(
                dataset,
                metrics=metrics,
                llm=self.llm,
                embeddings=self.embeddings,
                raise_exceptions=False,
            )
            return result
        except Exception as e:
            logger.error(f"Lỗi khi chấm điểm Ragas: {e}")
            return {"error": str(e)}