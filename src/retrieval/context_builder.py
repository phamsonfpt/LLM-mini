"""
Context Builder — Tầng Truy xuất
Đóng gói ngữ cảnh cuối cùng từ reranked chunks để đưa vào LLM Prompt.
"""
import logging
from typing import List, Dict, Any, Tuple

logger = logging.getLogger(__name__)

class ContextBuilder:
    """
    Nhận top chunks và tạo ra một đoạn văn bản Context hoàn chỉnh
    cùng với danh sách Citations (Trích dẫn) để trả về Frontend.
    """

    def build_context(self, chunks: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Build text context and citations from chunks.
        
        Returns:
            context_text (str): Văn bản tổng hợp để nhồi vào LLM Prompt
            citations (List[Dict]): Danh sách trích dẫn (Source metadata)
        """
        if not chunks:
            return "Không tìm thấy thông tin phù hợp trong tài liệu.", []

        context_parts = []
        citations = []

        for i, chunk in enumerate(chunks, start=1):
            source_marker = f"[Source {i}]"
            metadata = chunk.get("metadata", {})
            filename = metadata.get("source_file") or metadata.get("title") or metadata.get("source_url") or metadata.get("filename") or "Unknown"
            
            # Xây dựng đoạn text
            text_part = f"{source_marker} (Tài liệu: {filename}):\n{chunk['content']}\n"
            context_parts.append(text_part)

            # Lưu lại citation để frontend hiển thị
            citations.append({
                "id": i,
                "marker": source_marker,
                "filename": filename,
                "content": chunk["content"]
            })

        context_text = "\n".join(context_parts)
        logger.info(f"Context built with {len(chunks)} sources.")
        
        return context_text, citations
