import os
import logging
from datasets import Dataset

# Sửa lỗi module 'langchain_community.chat_models.vertexai' của ragas
import sys
import types
try:
    import langchain_community
    if not hasattr(langchain_community, 'chat_models'):
        langchain_community.chat_models = types.ModuleType('chat_models')
        sys.modules['langchain_community.chat_models'] = langchain_community.chat_models
    if not hasattr(langchain_community.chat_models, 'vertexai'):
        vertexai = types.ModuleType('vertexai')
        class ChatVertexAI: pass
        vertexai.ChatVertexAI = ChatVertexAI
        langchain_community.chat_models.vertexai = vertexai
        sys.modules['langchain_community.chat_models.vertexai'] = vertexai
except ImportError:
    pass

from ragas import evaluate
from ragas.metrics import (
    context_precision,
    context_recall,
    answer_relevancy,
    faithfulness,
)
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai import GoogleGenerativeAIEmbeddings

logger = logging.getLogger(__name__)

class RagasEvaluator:
    """Đánh giá RAG sử dụng Ragas."""
    
    def __init__(self, eval_model_type="gemini", api_key=None):
        """
        Khởi tạo Evaluator. Hỗ trợ "gemini" (mặc định) và "local" (chạy chậm nhưng offline).
        """
        if eval_model_type == "gemini":
            key = api_key or os.getenv("GOOGLE_API_KEY")
            if not key:
                logger.warning("Không tìm thấy GOOGLE_API_KEY. Ragas có thể không hoạt động.")
                raise ValueError("Cần API Key của Google Gemini!")
                
            self.llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", google_api_key=key)
            self.embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=key)
            
        elif eval_model_type == "local":
            logger.info("Đang cấu hình Ragas để sử dụng LOCAL LLM (cảnh báo: sẽ rất chậm và có thể lỗi parse JSON).")
            from langchain_openai import ChatOpenAI
            from langchain_community.embeddings import HuggingFaceEmbeddings
            from src.utils.config import settings
            
            self.llm = ChatOpenAI(
                model="qwen2.5:3b", 
                base_url=f"{settings.llama_server_url}/v1", 
                api_key="sk-local",
                max_tokens=2048,
                temperature=0.0
            )
            # Dùng embedding cục bộ giống dự án
            self.embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-base")
        else:
            raise ValueError(f"Không hỗ trợ loại model đánh giá: {eval_model_type}")
        
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
            context_recall,
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