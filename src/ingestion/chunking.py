import re
import numpy as np
from typing import List, Dict, Any
from .document_tree import DocumentNode, HeadingNode, ParagraphNode, Node
from ..utils.config import settings

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    return np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

class RecursiveCharacterChunker:
    """Chia văn bản dựa trên số lượng ký tự đệ quy (Nhanh, cho CPU)."""
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 150):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(self, text: str) -> List[str]:
        # Implement đơn giản: Cắt theo khoảng trắng để không cắt ngang từ
        words = text.split(' ')
        chunks = []
        current_chunk = []
        current_length = 0
        
        for word in words:
            word_len = len(word) + 1 # +1 cho khoảng trắng
            if current_length + word_len > self.chunk_size and current_length > 0:
                chunks.append(" ".join(current_chunk))
                # Giữ lại overlap
                overlap_words = []
                overlap_length = 0
                for w in reversed(current_chunk):
                    if overlap_length + len(w) + 1 <= self.chunk_overlap:
                        overlap_words.insert(0, w)
                        overlap_length += len(w) + 1
                    else:
                        break
                current_chunk = overlap_words
                current_length = overlap_length

            current_chunk.append(word)
            current_length += word_len
            
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        return chunks

class SemanticChunker:
    """Chia văn bản dựa trên khoảng cách ngữ nghĩa (Chậm, cần GPU)."""
    def __init__(self, embedder, threshold: float = 0.75):
        self.embedder = embedder
        self.threshold = threshold

    def chunk_text(self, text: str) -> List[str]:
        # Tách thành từng câu
        sentences = re.split(r'(?<=[.!?])\s+', text)
        if not sentences:
            return []
            
        # Tính embedding cho tất cả các câu một lúc (Batching)
        embeddings = self.embedder.embed_documents(sentences)
        
        chunks = []
        current_chunk = [sentences[0]]
        
        for i in range(1, len(sentences)):
            sim = cosine_similarity(embeddings[i-1], embeddings[i])
            # Nếu 2 câu giống nhau về ý tưởng (similarity > threshold), gộp chung
            if sim >= self.threshold:
                current_chunk.append(sentences[i])
            else:
                # Nếu khác chủ đề, cắt ra tạo chunk mới
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentences[i]]
                
        if current_chunk:
            chunks.append(" ".join(current_chunk))
            
        return chunks

class AdaptiveChunker:
    """Tự động lựa chọn phương pháp Chunking phù hợp với phần cứng."""
    
    def __init__(self, embedder=None):
        self.tier = self._get_hardware_tier()
        
        if self.tier in [1,2,3]:
            # Lấy embedder từ orchestrator nếu không truyền vào
            if embedder is None:
                try:
                    from ..utils.vram_orchestrator import get_orchestrator
                    embedder = get_orchestrator().get_embedder()
                except ImportError:
                    from ..ingestion.embedding import LocalEmbedder
                    embedder = LocalEmbedder()
            print("[AdaptiveChunker] Chế độ GPU: Kích hoạt Semantic Chunking.")
            self.chunker = SemanticChunker(embedder=embedder, threshold=0.75)
        else:
            print("[AdaptiveChunker] Chế độ CPU: Kích hoạt Recursive Character Chunking.")
            self.chunker = RecursiveCharacterChunker(
                chunk_size=settings.chunk_size, 
                chunk_overlap=settings.chunk_overlap
            )

    def _get_hardware_tier(self) -> int:
        from ..utils.hardware_profiler import ModelZooManager
        manager = ModelZooManager()
        return manager.get_tier()

    def process_document(self, document_node: DocumentNode) -> List[Dict[str, Any]]:
        """Duyệt Cây Tài liệu (DFS) và chunking các Paragraph, bảo lưu Metadata."""
        final_chunks = []
        
        def traverse(node: Node):
            # Chỉ chunking các node chứa văn bản dài như ParagraphNode
            if isinstance(node, ParagraphNode) and node.content.strip():
                # Băm nhỏ nội dung
                text_chunks = self.chunker.chunk_text(node.content)
                for chunk_text in text_chunks:
                    final_chunks.append({
                        "content": chunk_text,
                        "metadata": node.metadata # Metadata đã được kế thừa từ cha (Heading)
                    })
            
            # Duyệt tiếp các node con
            for child in node.children:
                traverse(child)

        traverse(document_node)
        return final_chunks
