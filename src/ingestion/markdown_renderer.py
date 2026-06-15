from .document_tree import Node, HeadingNode, ParagraphNode, TableNode, ImageNode, CodeBlockNode, ListNode, ListItemNode

class MarkdownRenderer:
    """Chuyển đổi Cây Tài Liệu (Document Tree) thành chuỗi Canonical Markdown chuẩn."""
    
    def render(self, node: Node) -> str:
        """Duyệt qua cây theo chiều sâu (DFS) và xây dựng chuỗi Markdown."""
        markdown_blocks = []
        
        # Xử lý nội dung của node hiện tại
        rendered_content = self._render_node(node)
        if rendered_content:
            markdown_blocks.append(rendered_content)
            
        # Xử lý các con của node
        for child in node.children:
            child_markdown = self.render(child)
            if child_markdown:
                markdown_blocks.append(child_markdown)
                
        return "\n\n".join(markdown_blocks)

    def _render_node(self, node: Node) -> str:
        if isinstance(node, HeadingNode):
            prefix = "#" * node.level
            return f"{prefix} {node.content}"
            
        elif isinstance(node, ParagraphNode):
            return node.content
            
        elif isinstance(node, TableNode):
            # TableNode content is expected to be a valid markdown table string
            return node.content
            
        elif isinstance(node, ImageNode):
            # Nếu có mô tả thêm thì gắn vào sau ảnh
            img_md = f"![{node.alt_text}]({node.url})"
            if node.content:
                img_md += f"\n*Mô tả ảnh: {node.content}*"
            return img_md
            
        elif isinstance(node, CodeBlockNode):
            return f"```{node.language}\n{node.content}\n```"
            
        elif isinstance(node, ListNode):
            # The list container itself doesn't render directly, its items do
            return ""
            
        elif isinstance(node, ListItemNode):
            # Simplify by rendering all items as unordered items for now
            # To support order, we would need to track indices from the parent ListNode
            return f"- {node.content}"
            
        return ""
