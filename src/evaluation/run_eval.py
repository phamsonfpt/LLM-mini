import os
import sys
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

import zipfile
import shutil
import pandas as pd
import uuid
import logging
import argparse
from tqdm import tqdm

from src.ingestion.parsers.markitdown_parser import MarkItDownParser
from src.ingestion.chunking import AdaptiveChunker
from src.ingestion.indexing import VectorStoreManager
from src.retrieval.search_engine import SearchEngine
from src.retrieval.bm25_index import get_bm25_index, BM25Document
from src.llm.llm_client import LLMEngine
from src.utils.vram_orchestrator import get_orchestrator
from src.evaluation.ragas_evaluator import RagasEvaluator
from src.db.session_manager import SessionManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

EVAL_NOTEBOOK_ID = "eval_notebook_rag_benchmark"
ZIP_PATH = os.path.join(os.path.dirname(__file__), "[Data]-Documents-PDFs (1).zip")
TEMP_EXTRACT_DIR = os.path.join(os.path.dirname(__file__), "eval_docs_temp")
CSV_PATH = os.path.join(os.path.dirname(__file__), "[Data]-Benchmark-Rag.csv")
OUTPUT_CSV = os.path.join(os.path.dirname(__file__), "eval_results.csv")

def extract_documents():
    """Giải nén tài liệu."""
    if not os.path.exists(ZIP_PATH):
        logger.error(f"Không tìm thấy file zip: {ZIP_PATH}")
        return False
        
    os.makedirs(TEMP_EXTRACT_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP_PATH, 'r') as zip_ref:
        zip_ref.extractall(TEMP_EXTRACT_DIR)
    logger.info(f"Đã giải nén tài liệu vào {TEMP_EXTRACT_DIR}")
    return True

def ingest_documents():
    """Nạp tài liệu vào notebook đánh giá."""
    session_manager = SessionManager()
    
    # Dọn dẹp tàn dư cũ (nếu có) để không bị nhân đôi dữ liệu gây tốn dung lượng
    try:
        session_manager.delete_notebook(EVAL_NOTEBOOK_ID)
    except Exception:
        pass
        
    session_manager.create_notebook(EVAL_NOTEBOOK_ID, "Eval Benchmark", is_private=True)
    
    vector_store = VectorStoreManager()
    try:
        vector_store.delete_notebook_chunks(EVAL_NOTEBOOK_ID)
    except Exception:
        pass
        
    parser = MarkItDownParser()
    
    # Đảm bảo GreenNode KHÔNG được nạp lên VRAM lúc này
    get_orchestrator().release_embedder()
    
    # Lấy danh sách file trong thư mục đã giải nén
    all_files = []
    for root, _, files in os.walk(TEMP_EXTRACT_DIR):
        for f in files:
            all_files.append(os.path.join(root, f))
            
    logger.info(f"Đang nạp {len(all_files)} tài liệu vào hệ thống...")
    
    # ========================================================
    # GIAI ĐOẠN 1: CHỈ PARSE TÀI LIỆU (ĐỌC ẢNH VÀ DỊCH TEXT)
    # ========================================================
    parsed_trees = []
    for filepath in tqdm(all_files, desc="Giai đoạn 1/2: Parsing (Dùng Moondream)"):
        filename = os.path.basename(filepath)
        try:
            tree = parser.parse(filepath, source_metadata={"notebook_id": EVAL_NOTEBOOK_ID})
            parsed_trees.append((filename, tree))
        except Exception as e:
            logger.error(f"Lỗi khi đọc file {filename}: {e}")
            
    # ========================================================
    # GIAI ĐOẠN 2: CHỈ CHUNKING VÀ EMBEDDING
    # ========================================================
    # Lúc này Moondream đã xong việc, tiến hành nạp GreenNode lên VRAM
    embedder = get_orchestrator().get_embedder()
    chunker = AdaptiveChunker(embedder=embedder)
    bm25_index = get_bm25_index(EVAL_NOTEBOOK_ID)
    
    for filename, tree in tqdm(parsed_trees, desc="Giai đoạn 2/2: Chunking & Embedding (Dùng GreenNode)"):
        try:
            chunks = chunker.process_document(tree)
            
            for chunk in chunks:
                chunk["metadata"]["notebook_id"] = EVAL_NOTEBOOK_ID
                chunk["metadata"]["filename"] = filename
                
            # Vector Indexing
            vector_store.index_chunks(chunks)
            
            # BM25 Indexing
            bm25_docs = [
                BM25Document(
                    chunk_id=c["metadata"].get("chunk_id", str(uuid.uuid4())),
                    text=c["content"],
                    metadata=c["metadata"]
                ) for c in chunks
            ]
            with bm25_index.transaction():
                bm25_index.load()
                bm25_index.add_documents(bm25_docs)
                bm25_index.save()
                
            session_manager.add_document(EVAL_NOTEBOOK_ID, filename, status="ready")
        except Exception as e:
            logger.error(f"Lỗi khi nạp file {filename}: {e}")
            
    # Giải phóng VRAM nếu cần
    get_orchestrator().release_all()

def evaluate(eval_model_type="gemini", api_key=None):
    """Chạy đánh giá."""
    df = pd.read_csv(CSV_PATH)
    questions = df['question'].tolist()
    ground_truths = df['ground truth'].tolist()
    
    # Kểm tra xem đã có bản lưu tạm (cache) chưa để đỡ phải chạy lại LLM tốn 1 tiếng
    cache_path = os.path.join(os.path.dirname(__file__), "temp_generated_answers.csv")
    if os.path.exists(cache_path):
        logger.info(f"Tìm thấy bản lưu tạm tại {cache_path}. Bỏ qua bước chạy LLM, tiến hành chấm điểm luôn!")
        cache_df = pd.read_csv(cache_path)
        answers = cache_df['answer'].tolist()
        import ast
        contexts_list = [ast.literal_eval(c) for c in cache_df['contexts'].tolist()]
    else:
        vector_store = VectorStoreManager()
        search_engine = SearchEngine(vector_store)
        llm = LLMEngine()
        
        answers = []
        contexts_list = []
        
        logger.info("Bắt đầu sinh câu trả lời cho benchmark dataset...")
        for q in tqdm(questions, desc="Generating Answers"):
            context_str, results = search_engine.retrieve(q, notebook_id=EVAL_NOTEBOOK_ID, top_k=5)
            
            # Lưu các đoạn context thuần túy cho Ragas
            extracted_contexts = [res["content"] for res in results]
            contexts_list.append(extracted_contexts)
            
            # Build prompt & generate
            prompt = llm.build_rag_prompt(q, context_str, history=[])
            system_prompt = "Bạn là một trợ lý ảo thông minh. Hãy trả lời câu hỏi dựa trên tài liệu được cung cấp."
            
            answer_generator = llm.generate(prompt, system_prompt, is_private=True)
            answer_text = "".join(list(answer_generator))
            answers.append(answer_text)
            
        get_orchestrator().release_all()
        
        # Lưu Cache tiến trình
        temp_df = pd.DataFrame({
            "question": questions,
            "answer": answers,
            "contexts": [str(c) for c in contexts_list],
            "ground_truth": ground_truths
        })
        temp_df.to_csv(cache_path, index=False, encoding='utf-8-sig')
        logger.info("Đã lưu kết quả sinh text tạm thời.")
    
    # Kiểm tra API KEY nếu dùng gemini
    final_api_key = api_key
    if eval_model_type == "gemini":
        if not final_api_key:
            final_api_key = os.getenv("GOOGLE_API_KEY")
        if not final_api_key:
            logger.warning("Không tìm thấy GOOGLE_API_KEY trong file .env hoặc từ khóa dòng lệnh.")
            final_api_key = input("🔑 Vui lòng nhập API Key của Gemini để tiếp tục chấm điểm: ").strip()
            if not final_api_key:
                logger.error("Không có API Key. Quá trình đánh giá bị hủy.")
                return

    # Chấm điểm Ragas
    try:
        evaluator = RagasEvaluator(eval_model_type=eval_model_type, api_key=final_api_key)
    except Exception as e:
        logger.error(f"Lỗi khởi tạo Evaluator: {e}")
        return
        
    results = evaluator.evaluate_batch(
        questions=questions,
        answers=answers,
        contexts=contexts_list,
        ground_truths=ground_truths
    )
    
    # Lưu kết quả
    if isinstance(results, dict) and "error" in results:
        logger.error(f"Đánh giá thất bại: {results['error']}")
    else:
        try:
            df_result = results.to_pandas()
            # Nối thêm ground truth vào dataframe
            df_result['ground_truth'] = ground_truths
            df_result.to_csv(OUTPUT_CSV, index=False, encoding='utf-8-sig')
            logger.info(f"Đã lưu kết quả chi tiết tại: {OUTPUT_CSV}")
            
            print("\n--- KẾT QUẢ ĐÁNH GIÁ TRUNG BÌNH ---")
            for k, v in results.items():
                print(f"{k}: {v:.4f}")
        except Exception as e:
            logger.error(f"Lỗi khi lưu kết quả: {e}")

def cleanup():
    """Dọn dẹp."""
    if os.path.exists(TEMP_EXTRACT_DIR):
        shutil.rmtree(TEMP_EXTRACT_DIR)
        logger.info(f"Đã dọn dẹp thư mục tạm {TEMP_EXTRACT_DIR}")
        
    # Có thể tùy chọn xóa EVAL_NOTEBOOK_ID khỏi session_manager và Qdrant nếu muốn

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run RAG Evaluation")
    parser.add_argument("--evaluator", type=str, default="gemini", choices=["gemini", "local"], help="Loại mô hình làm giám khảo (gemini hoặc local)")
    parser.add_argument("--api-key", type=str, default=None, help="API Key của Google Gemini (tùy chọn, ưu tiên hơn trong file .env)")
    args = parser.parse_args()

    logger.info("====== BẮT ĐẦU LUỒNG ĐÁNH GIÁ RAG ======")
    logger.info(f"Giám khảo được chọn: {args.evaluator.upper()}")
    
    # Kiểm tra xem có cần ingest không
    cache_path = os.path.join(os.path.dirname(__file__), "temp_generated_answers.csv")
    if not os.path.exists(cache_path):
        if extract_documents():
            ingest_documents()
    else:
        logger.info("Phát hiện cache tiến trình, bỏ qua bước Ingest.")
        
    evaluate(eval_model_type=args.evaluator, api_key=args.api_key)
    cleanup()
    logger.info("====== HOÀN TẤT ======")
