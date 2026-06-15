import os
from typing import Optional
from markitdown import MarkItDown

from ..document_tree import DocumentNode
from .markdown_parser import MarkdownParser

class MarkItDownParser:
    """Sử dụng thư viện MarkItDown (Microsoft) để parse PDF, Office, Excel, v.v. thành Document Tree."""
    
    def __init__(self):
        self.md_parser = MarkdownParser()
        self.markitdown = MarkItDown()

    def parse(self, file_path: str, source_metadata: Optional[dict] = None) -> DocumentNode:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Không tìm thấy file: {file_path}")
            
        # 1. Parse tệp thô thành Markdown string thông qua MarkItDown
        try:
            result = self.markitdown.convert(file_path)
            raw_markdown = result.text_content
        except Exception as e:
            raise RuntimeError(f"Lỗi khi MarkItDown xử lý file {file_path}: {str(e)}")

        # 2. Xây dựng metadata
        meta = source_metadata or {}
        meta["source_file"] = os.path.basename(file_path)
        meta["parser"] = "MarkItDownParser"

        # 3. Chuyển chuỗi Markdown thô thành Cây phân cấp (Document Tree)
        document_tree = self.md_parser.parse(raw_markdown, source_metadata=meta)
        
        return document_tree
