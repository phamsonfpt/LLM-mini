import os
from fastapi import FastAPI, File, UploadFile, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..ingestion.parsers.markitdown_parser import MarkItDownParser
from ..ingestion.parsers.web_parser import WebParser
from ..ingestion.chunking import AdaptiveChunker
from ..ingestion.embedding import LocalEmbedder
from ..ingestion.indexing import VectorStoreManager
from ..retrieval.search_engine import SearchEngine
from ..generation.llm_engine import LLMEngine

app = FastAPI(title="NotebookLM Mini API")

# Setup CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Instances (Lazy load)
embedder = None
vector_store = None
search_engine = None
llm_engine = None

@app.on_event("startup")
def startup_event():
    global embedder, vector_store, search_engine, llm_engine
    print("🚀 Khởi động các Module Lõi của hệ thống...")
    embedder = LocalEmbedder()
    vector_store = VectorStoreManager(embedder=embedder)
    search_engine = SearchEngine(vector_store=vector_store)
    llm_engine = LLMEngine()

class ChatRequest(BaseModel):
    query: str

@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    """Xử lý câu hỏi của người dùng và stream câu trả lời."""
    # 1. Truy xuất dữ liệu (Retrieval)
    context = search_engine.retrieve(request.query)
    
    # 2. Xây dựng Prompt (Generation)
    rag_prompt = llm_engine.build_rag_prompt(request.query, context)
    system_prompt = "Bạn là một trợ lý ảo thông minh. Hãy trả lời câu hỏi dựa trên tài liệu được cung cấp."
    
    # 3. Stream phản hồi
    return StreamingResponse(
        llm_engine.generate(rag_prompt, system_prompt),
        media_type="text/event-stream"
    )

@app.post("/api/ingest/url")
async def ingest_url(url: str):
    """Nạp dữ liệu từ URL."""
    parser = WebParser()
    tree = parser.parse(url)
    
    chunker = AdaptiveChunker(embedder=embedder)
    chunks = chunker.process_document(tree)
    
    vector_store.index_chunks(chunks)
    return {"status": "success", "chunks_indexed": len(chunks)}

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
