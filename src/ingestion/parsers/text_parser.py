import os
from typing import Optional

from ..document_tree import DocumentNode, HeadingNode, ParagraphNode

class TextParser:
    """Parser xử lý văn bản thô (TXT file hoặc chuỗi) bằng phương pháp Heuristics."""

    def __init__(self):
        pass

    def _is_heading(self, line: str) -> bool:
        """Kiểm tra xem một dòng có vẻ là tiêu đề hay không."""
        # Nếu dòng ngắn (< 100 ký tự) và viết hoa toàn bộ hoặc không kết thúc bằng dấu chấm câu
        if len(line) < 100 and (line.isupper() or line[-1] not in ['.', '!', '?']):
            return True
        return False

    def parse(self, text_or_path: str, source_metadata: Optional[dict] = None) -> DocumentNode:
        text_content = ""
        source_name = "Raw Text"

        if os.path.exists(text_or_path):
            source_name = os.path.basename(text_or_path)
            with open(text_or_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
        else:
            text_content = text_or_path

        # Xây dựng metadata
        meta = source_metadata or {}
        meta["source_file"] = source_name
        meta["parser"] = "TextParser"

        # Khởi tạo Document Tree
        doc_node = DocumentNode(metadata=meta)
        
        # Tách văn bản thành các khối dựa vào dòng trống
        blocks = text_content.split('\n\n')

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            # Phân loại khối
            if '\n' not in block and self._is_heading(block):
                # Là tiêu đề
                doc_node.add_child(HeadingNode(level=2, content=block))
            else:
                # Là đoạn văn thông thường
                # Xóa bớt các dấu ngắt dòng không cần thiết bên trong đoạn
                clean_paragraph = " ".join(block.split())
                doc_node.add_child(ParagraphNode(content=clean_paragraph))

        return doc_node
