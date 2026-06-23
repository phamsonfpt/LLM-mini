import os
import uuid
from typing import List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, PointStruct
from ..utils.config import settings

class VectorStoreManager:
    """Quản lý việc lưu trữ Vector vào Qdrant Local."""
    
    def __init__(self, embedder=None):
        self._embedder_ref = embedder  # Có thể None, sẽ lazy load qua orchestrator
        self._vector_size = None
        
        # Tạo thư mục chứa database nếu chưa có
        os.makedirs(settings.storage_dir, exist_ok=True)
        
        # Khởi tạo Qdrant Local Mode (Ghi trực tiếp ra ổ cứng, không cần Docker)
        self.client = QdrantClient(path=str(settings.storage_dir))
        self.collection_name = settings.qdrant_collection
        self._collection_initialized = False

    def _get_embedder(self):
        """Lấy embedder: ưu tiên orchestrator, fallback về reference truyền vào."""
        try:
            from ..utils.vram_orchestrator import get_orchestrator
            return get_orchestrator().get_embedder()
        except ImportError:
            if self._embedder_ref is not None:
                return self._embedder_ref
            from ..ingestion.embedding import LocalEmbedder
            self._embedder_ref = LocalEmbedder()
            return self._embedder_ref

    @property
    def vector_size(self):
        if self._vector_size is None:
            embedder = self._get_embedder()
            dummy_vector = embedder.embed_query("test")
            self._vector_size = len(dummy_vector)
        return self._vector_size

    @property
    def embedder(self):
        return self._get_embedder()

    def _init_collection(self):
        """Tạo collection nếu chưa tồn tại."""
        if self._collection_initialized:
            return
        collections = self.client.get_collections().collections
        exists = any(c.name == self.collection_name for c in collections)
        
        if not exists:
            print(f"[Qdrant] Đang tạo Collection mới: {self.collection_name} (Size: {self.vector_size})")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.vector_size, distance=Distance.COSINE),
            )
        else:
            print(f"[Qdrant] Đã kết nối tới Collection: {self.collection_name}")
        self._collection_initialized = True

    def index_chunks(self, chunks: List[Dict[str, Any]]):
        """Nhúng và lưu các đoạn văn bản vào Database."""
        if not chunks:
            return
        
        self._init_collection()
            
        print(f"[Qdrant] Đang tính toán Vector cho {len(chunks)} đoạn văn bản...", flush=True)
        texts = [chunk["content"] for chunk in chunks]
        embeddings = self.embedder.embed_documents(texts)
        
        points = []
        for i, chunk in enumerate(chunks):
            point = PointStruct(
                id=str(uuid.uuid4()), # Sinh ID duy nhất
                vector=embeddings[i],
                payload={
                    "content": chunk["content"],
                    **chunk["metadata"] # Gắn kèm siêu dữ liệu (Metadata)
                }
            )
            points.append(point)
            
        print(f"[Qdrant] Đang lưu {len(points)} Vectors vào Database...", flush=True)
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
        print("[Qdrant] Lưu dữ liệu hoàn tất!", flush=True)

    def delete_notebook_chunks(self, notebook_id: str):
        """Xóa tất cả các chunk thuộc về một notebook."""
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="notebook_id",
                        match=MatchValue(value=notebook_id)
                    )
                ]
            )
        )

    def delete_document_chunks(self, notebook_id: str, filename: str):
        """Xóa tất cả các chunk thuộc về một tài liệu trong notebook."""
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue, FilterSelector
        # Qdrant delete bằng filter
        # Chúng ta xóa các chunk có notebook_id = notebook_id VÀ (source_file = filename HOẶC title = filename HOẶC source_url = filename)
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(key="notebook_id", match=MatchValue(value=notebook_id))
                ],
                should=[
                    FieldCondition(key="source_file", match=MatchValue(value=filename)),
                    FieldCondition(key="title", match=MatchValue(value=filename)),
                    FieldCondition(key="source_url", match=MatchValue(value=filename))
                ]
            )
        )

    def search(self, query: str, limit: int = 5, notebook_id: str = None) -> List[Dict[str, Any]]:
        """Tìm kiếm dữ liệu tương tự."""
        from qdrant_client.http.models import Filter, FieldCondition, MatchValue
        
        self._init_collection()
        query_vector = self.embedder.embed_query(query)
        
        query_filter = None
        if notebook_id:
            query_filter = Filter(
                must=[
                    FieldCondition(
                        key="notebook_id",
                        match=MatchValue(value=notebook_id)
                    )
                ]
            )
        
        res = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=limit
        )
        hits = res.points
        
        results = []
        for hit in hits:
            results.append({
                "score": hit.score,
                "content": hit.payload.get("content", ""),
                "metadata": {k: v for k, v in hit.payload.items() if k != "content"}
            })
        return results
