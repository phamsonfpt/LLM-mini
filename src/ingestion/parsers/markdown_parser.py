import re
from typing import List, Optional
from ..document_tree import DocumentNode, HeadingNode, ParagraphNode, CodeBlockNode, Node

class MarkdownParser:
    """Phân tích chuỗi Markdown thô thành Cây Tài Liệu (Document Tree)."""
    
    def parse(self, markdown_text: str, source_metadata: dict = None) -> DocumentNode:
        root = DocumentNode(metadata=source_metadata or {})
        
        # Một regex đơn giản để tách Markdown thành các block
        # Tìm các heading (# Heading)
        blocks = re.split(r'(?m)^(#+ .*)$', markdown_text)
        
        current_parent: Node = root
        heading_stack: List[HeadingNode] = []
        
        for block in blocks:
            block = block.strip()
            if not block:
                continue
                
            # Kiểm tra xem block có phải là heading không
            heading_match = re.match(r'^(#+)\s+(.*)$', block)
            if heading_match:
                level = len(heading_match.group(1))
                title = heading_match.group(2).strip()
                heading_node = HeadingNode(level=level, content=title)
                
                # Quản lý cấu trúc phân cấp (Hierarchical Tree)
                # Tìm parent phù hợp dựa vào level
                while heading_stack and heading_stack[-1].level >= level:
                    heading_stack.pop()
                    
                if heading_stack:
                    heading_stack[-1].add_child(heading_node)
                else:
                    root.add_child(heading_node)
                    
                heading_stack.append(heading_node)
                current_parent = heading_node
            else:
                # Nếu không phải heading, nó có thể là paragraph hoặc code block
                if block.startswith("```"):
                    # Xử lý code block đơn giản
                    lines = block.split('\n')
                    lang = lines[0].replace('```', '').strip()
                    code = '\n'.join(lines[1:-1]) if len(lines) > 2 else ""
                    current_parent.add_child(CodeBlockNode(language=lang, code=code))
                else:
                    # Chuyển thành Paragraph
                    current_parent.add_child(ParagraphNode(content=block))
                    
        return root
