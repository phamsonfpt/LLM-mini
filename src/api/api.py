import os
import json
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from fastapi import FastAPI, File, UploadFile, BackgroundTasks, Form, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from src.ingestion.parsers.markitdown_parser import MarkItDownParser
from src.ingestion.parsers.web_parser import WebParser
from src.ingestion.chunking import AdaptiveChunker
from src.ingestion.embedding import LocalEmbedder
from src.ingestion.indexing import VectorStoreManager
from src.retrieval.search_engine import SearchEngine
from src.llm.llm_client import LLMEngine
from src.db.session_manager import SessionManager
from src.learning.guide_generator import GuideGenerator
from src.learning.podcast_generator import PodcastGenerator
from src.retrieval.bm25_index import get_bm25_index, BM25Document, delete_bm25_folder
import uuid
from cachetools import TTLCache

app = FastAPI(title="NotebookLM Mini API")

# Setup CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

import threading

# Global Instances (Lazy load)
vector_store = None
search_engine = None
llm_engine = None
session_manager = None

init_lock = threading.RLock()

# Cache LRU + TTL: Tối đa 200 câu hỏi, tự động xóa sau 60 phút không truy cập
_QUERY_CACHE = TTLCache(maxsize=200, ttl=3600)
cache_lock = threading.Lock()

def clear_cache(notebook_id: str):
    with cache_lock:
        keys_to_delete = [k for k in list(_QUERY_CACHE.keys()) if k.startswith(f"{notebook_id}_")]
        for k in keys_to_delete:
            if k in _QUERY_CACHE:
                del _QUERY_CACHE[k]

def _index_all_chunks(notebook_id: str, chunks: list):
    if not chunks:
        return

    # Xác định tất cả tên file duy nhất trong danh sách chunks để dọn dẹp trước
    filenames = list(set(chunk["metadata"].get("filename") for chunk in chunks if chunk.get("metadata", {}).get("filename")))

    store = get_vector_store()
    bm25_index = get_bm25_index(notebook_id)

    # Dọn dẹp chunk cũ của các file này trong Qdrant và BM25 trước khi index mới (Tránh trùng lặp - Bug 1)
    for filename in filenames:
        print(f"[Indexing] Đang dọn dẹp chunk cũ của tài liệu '{filename}' trong notebook '{notebook_id}'...", flush=True)
        store.delete_document_chunks(notebook_id, filename)
        try:
            bm25_index.load()
            bm25_index.remove_document(filename)
            bm25_index.save()
        except Exception as e:
            print(f"[BM25] Lỗi dọn dẹp chunk cũ cho '{filename}': {e}", flush=True)

    # Vector Indexing
    store.index_chunks(chunks)
    
    # BM25 Indexing
    bm25_docs = [
        BM25Document(
            chunk_id=chunk["metadata"].get("chunk_id", str(uuid.uuid4())),
            text=chunk["content"],
            metadata=chunk["metadata"]
        ) for chunk in chunks
    ]
    try:
        bm25_index.load()
        bm25_index.add_documents(bm25_docs)
        bm25_index.save()
    except Exception as e:
        print(f"[BM25] Lỗi khi thêm tài liệu vào index: {e}", flush=True)

@app.on_event("startup")
def startup_event():
    global session_manager
    print("[System] Khoi dong cac Module Loi cua he thong...")
    # Khởi tạo DB manager trước vì nó rất nhẹ và cần thiết ngay
    session_manager = SessionManager()

def get_embedder():
    from src.utils.vram_orchestrator import get_orchestrator
    return get_orchestrator().get_embedder()

def get_vector_store():
    global vector_store
    with init_lock:
        if vector_store is None:
            vector_store = VectorStoreManager()
    return vector_store

def get_search_engine():
    global search_engine
    with init_lock:
        if search_engine is None:
            search_engine = SearchEngine(vector_store=get_vector_store())
    return search_engine

def get_llm_engine():
    global llm_engine
    with init_lock:
        if llm_engine is None:
            llm_engine = LLMEngine()
    return llm_engine

class NotebookCreate(BaseModel):
    id: str
    title: str
    is_private: bool = True
    gemini_api_key: Optional[str] = None

@app.post("/api/notebooks")
def create_notebook(data: NotebookCreate):
    session_manager.create_notebook(data.id, data.title, data.is_private, data.gemini_api_key)
    return {"status": "success", "notebook": data.dict()}

@app.get("/api/notebooks")
def list_notebooks():
    return session_manager.list_notebooks()

@app.delete("/api/notebooks/{notebook_id}")
def delete_notebook(notebook_id: str):
    session_manager.delete_notebook(notebook_id)
    store = get_vector_store()
    store.delete_notebook_chunks(notebook_id)
    delete_bm25_folder(notebook_id)
    clear_cache(notebook_id)
    return {"status": "success"}

@app.get("/api/notebooks/{notebook_id}/documents")
def get_documents(notebook_id: str):
    return session_manager.get_documents(notebook_id)

@app.delete("/api/notebooks/{notebook_id}/documents")
def delete_document(notebook_id: str, filename: str):
    session_manager.delete_document(notebook_id, filename)
    store = get_vector_store()
    store.delete_document_chunks(notebook_id, filename)
    
    # Xóa khỏi BM25
    bm25_index = get_bm25_index(notebook_id)
    try:
        bm25_index.load()
        bm25_index.remove_document(filename)
        bm25_index.save()
    except Exception as e:
        print(f"Error removing from BM25: {e}")
    
    clear_cache(notebook_id)
    return {"status": "success"}

@app.get("/api/notebooks/{notebook_id}/messages")
def get_messages(notebook_id: str):
    return session_manager.get_chat_history(notebook_id)

@app.get("/api/notebooks/{notebook_id}/study-guide")
def get_study_guide(notebook_id: str):
    return session_manager.get_study_guide(notebook_id)

class ChatRequest(BaseModel):
    query: str
    notebook_id: str

def is_overview_query(query: str) -> bool:
    import re
    q = query.lower().strip()
    # Danh sách từ khóa có sử dụng ranh giới từ (word boundaries) để tránh match sai (như summary statistics)
    keywords = [
        r"\btóm tắt\b", r"\btom tat\b",
        r"\btổng quan\b", r"\btong quan\b",
        r"\bkhái quát\b", r"\bkhai quat\b",
        r"\bnội dung chính\b", r"\bnoi dung chinh\b",
        r"\bnói về cái gì\b", r"\bnoi ve cai gi\b",
        r"\bnói về gì\b", r"\bnoi ve gi\b",
        r"\bchủ đề\b", r"\bchu de\b",
        r"\btrong file này\b", r"\btrong file nay\b",
        r"\btrong tài liệu\b", r"\btrong tai lieu\b",
        r"\bfile này có\b", r"\bfile nay co\b",
        r"\btài liệu này có\b", r"\btai lieu nay co\b",
        r"\bcó gì\b", r"\bco gi\b",
        r"\bsummary\b", r"\bsummarize\b", r"\boverview\b",
        r"\bwhat is in this\b", r"\babout this file\b", r"\babout this document\b"
    ]
    return any(re.search(kw, q) for kw in keywords)

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Xử lý câu hỏi của người dùng và stream câu trả lời."""
    notebook = session_manager.get_notebook(request.notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
        
    # Lưu tin nhắn người dùng
    session_manager.save_message(request.notebook_id, "user", request.query)
    
    # Hàm stream và lưu tin nhắn AI
    async def stream_and_save():
        full_response = ""
        is_private = notebook.get('is_private', True)
        api_key = notebook.get('gemini_api_key')
        citations = []
        
        import hashlib
        docs = session_manager.get_documents(request.notebook_id)
        # Tạo signature kết hợp số lượng tài liệu và chi tiết từng tài liệu (filename, status, created_at)
        doc_signature = f"count:{len(docs)}," + ",".join([f"{d['filename']}:{d['status']}:{d.get('created_at', '')}" for d in docs])
        doc_hash = hashlib.md5(doc_signature.encode('utf-8')).hexdigest()
        cache_key = f"{request.notebook_id}_{doc_hash}_{request.query}"
        
        # --- CHECK CACHE ---
        with cache_lock:
            cached_data = _QUERY_CACHE.get(cache_key)
            
        if cached_data:
            full_response = cached_data["response"]
            citations = cached_data["citations"]
            
            yield f"data: {json.dumps({'type': 'status', 'message': 'Đang lấy dữ liệu từ Cache...'})}\n\n"
            if citations:
                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"
                
            # Fake streaming for cached content
            chunk_size = 20
            import asyncio
            for i in range(0, len(full_response), chunk_size):
                chunk = full_response[i:i+chunk_size]
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
                await asyncio.sleep(0.02)
            
            yield f"data: {json.dumps({'type': 'status', 'message': ''})}\n\n"
            session_manager.save_message(request.notebook_id, "assistant", full_response, citations=citations)
            return
            
        try:
            # Gửi status: Đang tìm kiếm
            yield f"data: {json.dumps({'type': 'status', 'message': 'Đang tìm kiếm dữ liệu trong Sổ tay...'})}\n\n"
            
            # 1. Truy xuất dữ liệu (Retrieval)
            engine = get_search_engine()
            context_str, results = engine.retrieve(request.query, notebook_id=request.notebook_id)
            
            # Gửi status: Phân tích
            yield f"data: {json.dumps({'type': 'status', 'message': 'Đang đọc và phân tích ngữ cảnh...'})}\n\n"
            
            # Check if this is an overview query
            is_overview = is_overview_query(request.query)
            if is_overview:
                study_guide = session_manager.get_study_guide(request.notebook_id)
                if study_guide and study_guide.get("summary"):
                    summary_text = study_guide["summary"]
                    # Prepend study guide summary to context_str
                    context_str = f"[Tổng quan tài liệu]:\n{summary_text}\n\n---\n\n{context_str}"
                    citations.append({
                        "marker": "[Tổng quan]",
                        "filename": "Tóm tắt tổng quan",
                        "content": summary_text
                    })
            
            for doc in results:
                citations.append({
                    "marker": f"[{len(citations)+1}]",
                    "filename": doc['metadata'].get('source_file') or doc['metadata'].get('title') or doc['metadata'].get('source_url') or doc['metadata'].get('filename') or 'Tài liệu',
                    "content": doc.get("content", "")
                })
            
            if citations:
                yield f"data: {json.dumps({'type': 'citations', 'citations': citations})}\n\n"

            # 2. Xây dựng Prompt
            llm = get_llm_engine()
            rag_prompt = llm.build_rag_prompt(request.query, context_str)
            system_prompt = (
                "Bạn là trợ lý ảo thông minh NotebookLM Mini. "
                "Nhiệm vụ của bạn là trả lời câu hỏi dựa trên tài liệu được cung cấp. "
                "Hãy trình bày câu trả lời một cách tự nhiên, mạch lạc và tổng hợp thông tin từ nhiều nguồn/đoạn văn bản khác nhau. "
                "TRÁNH liệt kê máy móc từng nguồn một (ví dụ: không viết 'Nguồn 1: ..., Nguồn 2: ...'). "
                "Nếu cùng đề cập đến một tài liệu, hãy tổng hợp thành các đoạn văn trôi chảy và chỉ chú thích nguồn bằng các ký hiệu [1], [2] hoặc [Tổng quan] ở cuối câu/ý tương ứng."
            )
            
            # Gửi status: Gọi AI
            yield f"data: {json.dumps({'type': 'status', 'message': 'AI đang suy nghĩ câu trả lời...'})}\n\n"

            # 3. Gửi từng chunk text (Hỗ trợ Batching tự nhiên)
            from fastapi.concurrency import iterate_in_threadpool
            async for chunk in iterate_in_threadpool(llm.generate(rag_prompt, system_prompt, is_private=is_private, gemini_api_key=api_key)):
                full_response += chunk
                yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
                
            # Xóa status khi hoàn thành
            yield f"data: {json.dumps({'type': 'status', 'message': ''})}\n\n"
            
            # --- LƯU CACHE ---
            with cache_lock:
                _QUERY_CACHE[cache_key] = {
                    "response": full_response,
                    "citations": citations
                }
            
        except Exception as e:
            yield f"data: {json.dumps({'type': 'chunk', 'text': f'Lỗi hệ thống: {e}'})}\n\n"
        finally:
            from src.utils.vram_orchestrator import get_orchestrator
            get_orchestrator().release_all()
            session_manager.save_message(request.notebook_id, "assistant", full_response, citations=citations)

    # 3. Stream phản hồi
    return StreamingResponse(
        stream_and_save(),
        media_type="text/event-stream"
    )

@app.post("/api/ingest/url")
async def ingest_url(background_tasks: BackgroundTasks, notebook_id: str = Form(...), url: str = Form(...)):
    """Nạp dữ liệu từ URL."""
    parser = WebParser()
    tree = parser.parse(url)
    tree.metadata["notebook_id"] = notebook_id
    
    filename = tree.metadata.get("title", url)
    
    from src.ingestion.chunking import AdaptiveChunker
    print(f"[Chunking] Bắt đầu chia nhỏ URL: {url}...", flush=True)
    chunker = AdaptiveChunker(embedder=get_embedder())
    chunks = chunker.process_document(tree)
    print(f"[Chunking] Đã chia thành {len(chunks)} đoạn văn bản.", flush=True)
    
    for chunk in chunks:
        chunk["metadata"]["notebook_id"] = notebook_id
        chunk["metadata"]["filename"] = filename
    
    _index_all_chunks(notebook_id, chunks)
    session_manager.add_document(notebook_id, filename, status="ready")
    clear_cache(notebook_id)
    
    # Giải phóng Embedding ngay sau khi index xong để tối ưu RAM
    try:
        from src.utils.vram_orchestrator import get_orchestrator
        get_orchestrator().release_all()
    except Exception as e:
        print(f"Error releasing resources: {e}")
    
    document_text = "\n\n".join([chunk["content"] for chunk in chunks])
    notebook = session_manager.get_notebook(notebook_id)
    is_private = notebook.get('is_private', True) if notebook else True
    api_key = notebook.get('gemini_api_key') if notebook else None

    # Sinh Study Guide ngầm
    llm = get_llm_engine()
    guide_gen = GuideGenerator(llm, session_manager)
    background_tasks.add_task(
        guide_gen.generate, 
        notebook_id, 
        document_text, 
        is_private=is_private,
        gemini_api_key=api_key
    )
    
    return {"status": "success", "chunks_indexed": len(chunks)}

@app.post("/api/ingest/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    notebook_id: str = Form(...), 
    file: UploadFile = File(...)
):
    upload_dir = "uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    
    with open(file_path, "wb") as f:
        f.write(await file.read())
        
    if file.filename.lower().endswith(('.mp3', '.wav', '.flac', '.ogg', '.m4a')):
        from src.ingestion.parsers.audio_parser import AudioParser
        parser = AudioParser()
    else:
        parser = MarkItDownParser()
        
    tree = parser.parse(file_path)
    
    tree.metadata["notebook_id"] = notebook_id
    filename = file.filename
    
    from src.ingestion.chunking import AdaptiveChunker
    print(f"[Chunking] Bắt đầu chia nhỏ tài liệu: {file.filename}...", flush=True)
    chunker = AdaptiveChunker(embedder=get_embedder())
    chunks = chunker.process_document(tree)
    print(f"[Chunking] Đã chia thành {len(chunks)} đoạn văn bản.", flush=True)
    
    for chunk in chunks:
        chunk["metadata"]["notebook_id"] = notebook_id
        chunk["metadata"]["filename"] = file.filename
    
    _index_all_chunks(notebook_id, chunks)
    session_manager.add_document(notebook_id, file.filename, status="ready")
    clear_cache(notebook_id)
    
    # Giải phóng Embedding ngay sau khi index xong để tối ưu RAM
    try:
        from src.utils.vram_orchestrator import get_orchestrator
        get_orchestrator().release_all()
    except Exception as e:
        print(f"Error releasing resources: {e}")
    
    document_text = "\n\n".join([chunk["content"] for chunk in chunks])
    notebook = session_manager.get_notebook(notebook_id)
    is_private = notebook.get('is_private', True) if notebook else True
    api_key = notebook.get('gemini_api_key') if notebook else None

    # Sinh Study Guide ngầm
    llm = get_llm_engine()
    guide_gen = GuideGenerator(llm, session_manager)
    background_tasks.add_task(
        guide_gen.generate, 
        notebook_id, 
        document_text, 
        is_private=is_private,
        gemini_api_key=api_key
    )
    
    return {"status": "success", "chunks_indexed": len(chunks)}

@app.post("/api/podcast/generate")
async def generate_podcast(background_tasks: BackgroundTasks, notebook_id: str = Form(...)):
    notebook = session_manager.get_notebook(notebook_id)
    is_private = notebook.get('is_private', True) if notebook else True
    api_key = notebook.get('gemini_api_key') if notebook else None
    
    llm = get_llm_engine()
    generator = PodcastGenerator(llm, session_manager)
    background_tasks.add_task(
        generator.generate_podcast, 
        notebook_id,
        is_private=is_private,
        gemini_api_key=api_key
    )
    return {"status": "processing"}

@app.post("/api/evaluate")
async def evaluate_knowledge(notebook_id: str = Form(...)):
    notebook = session_manager.get_notebook(notebook_id)
    if not notebook:
        raise HTTPException(status_code=404, detail="Notebook not found")
        
    is_private = notebook.get('is_private', True)
    api_key = notebook.get('gemini_api_key')
    
    from src.learning.evaluator import Evaluator
    llm = get_llm_engine()
    evaluator = Evaluator(llm, session_manager)
    
    try:
        from fastapi.concurrency import run_in_threadpool
        metrics = await run_in_threadpool(evaluator.evaluate_knowledge, notebook_id, is_private=is_private, gemini_api_key=api_key)
        return {"status": "success", "metrics": metrics}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

# Phục vụ giao diện React (Frontend SPA)
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")

if os.path.exists(FRONTEND_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")
    
    @app.get("/{catchall:path}")
    def serve_react_app(catchall: str):
        """Bắt mọi route không có trong API và trả về index.html của React Router."""
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"error": "Frontend chưa được build. Vui lòng chạy npm run build trong thư mục frontend."}
else:
    @app.get("/")
    def no_frontend():
        return {"message": "Hệ thống đang chạy ngầm. Giao diện React chưa được build (thiếu thư mục frontend/dist)."}
