from typing import List, Dict, Any
from ..ingestion.indexing import VectorStoreManager
from ..utils.config import settings
from src.utils.telemetry import trace_execution

class SearchEngine:
    """Công cụ truy xuất dữ liệu từ Vector Database (RAG Retrieval)."""
    def __init__(self, vector_store: VectorStoreManager):
        self.vector_store = vector_store

    @trace_execution(event_name="retrieval", module="search_engine")
    def retrieve(self, query: str, notebook_id: str, top_k: int = 5) -> str:
        """
        Tìm kiếm các đoạn văn bản liên quan và định dạng chúng thành Context cho LLM.
        """
        results = self.vector_store.search(query, limit=top_k, notebook_id=notebook_id)
        
        if not results:
            return "Không tìm thấy thông tin liên quan trong tài liệu.", []

        context_parts = []
        for i, res in enumerate(results):
            content = res["content"]
            metadata = res["metadata"]
            source = metadata.get("source_file") or metadata.get("title") or metadata.get("source_url") or metadata.get("filename") or "Tài liệu"
            heading = metadata.get("heading_level_1", "")
            
            # Formatting the chunk for LLM
            context_parts.append(f"[Nguồn {i+1} - {source}]:\n{content}")
            
        return "\n\n---\n\n".join(context_parts), results
