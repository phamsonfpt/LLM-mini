from typing import List, Dict, Any, Optional

class Node:
    """Lớp cơ sở cho tất cả các nút trong Cây Tài Liệu."""
    def __init__(self, node_type: str, content: str = "", metadata: Optional[Dict[str, Any]] = None):
        self.node_type = node_type
        self.content = content
        self.metadata = metadata or {}
        self.children: List['Node'] = []
        self.parent: Optional['Node'] = None

    def add_child(self, child: 'Node'):
        child.parent = self
        # Kế thừa metadata từ cha
        merged_meta = self.metadata.copy()
        merged_meta.update(child.metadata)
        child.metadata = merged_meta
        self.children.append(child)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.node_type,
            "content": self.content,
            "metadata": self.metadata,
            "children": [child.to_dict() for child in self.children]
        }

class DocumentNode(Node):
    def __init__(self, metadata: Optional[Dict[str, Any]] = None):
        super().__init__("Document", metadata=metadata)

class HeadingNode(Node):
    def __init__(self, level: int, content: str, metadata: Optional[Dict[str, Any]] = None):
        super().__init__("Heading", content, metadata)
        self.level = level
        self.metadata["heading_level"] = level

class ParagraphNode(Node):
    def __init__(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        super().__init__("Paragraph", content, metadata)

class TableNode(Node):
    def __init__(self, markdown_table: str, metadata: Optional[Dict[str, Any]] = None):
        super().__init__("Table", markdown_table, metadata)

class ImageNode(Node):
    def __init__(self, alt_text: str, url: str, description: str = "", metadata: Optional[Dict[str, Any]] = None):
        super().__init__("Image", description, metadata)
        self.alt_text = alt_text
        self.url = url
        self.metadata["image_url"] = url

class CodeBlockNode(Node):
    def __init__(self, language: str, code: str, metadata: Optional[Dict[str, Any]] = None):
        super().__init__("CodeBlock", code, metadata)
        self.language = language
        self.metadata["code_language"] = language

class ListNode(Node):
    def __init__(self, is_ordered: bool = False, metadata: Optional[Dict[str, Any]] = None):
        super().__init__("List", metadata=metadata)
        self.is_ordered = is_ordered

class ListItemNode(Node):
    def __init__(self, content: str, metadata: Optional[Dict[str, Any]] = None):
        super().__init__("ListItem", content, metadata)
