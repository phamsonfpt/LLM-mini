import os
import re
import tempfile
import logging
from typing import Optional
from markitdown import MarkItDown

from ..document_tree import DocumentNode
from .markdown_parser import MarkdownParser

logger = logging.getLogger(__name__)

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

        # 2. Hậu xử lý: Nếu là PDF, trích xuất ảnh và dùng LLaVA phân tích
        if file_path.lower().endswith('.pdf'):
            raw_markdown = self._enrich_images_from_pdf(file_path, raw_markdown)
            
        # 3. Hậu xử lý cho các file khác (DOCX, PPTX, XLSX, HTML): 
        # MarkItDown thường nhúng ảnh dưới dạng Base64 (data:image/png;base64,...)
        raw_markdown = self._enrich_base64_images(raw_markdown)

        # 4. Xây dựng metadata
        meta = source_metadata or {}
        meta["source_file"] = os.path.basename(file_path)
        meta["parser"] = "MarkItDownParser"

        # 4. Chuyển chuỗi Markdown thô thành Cây phân cấp (Document Tree)
        document_tree = self.md_parser.parse(raw_markdown, source_metadata=meta)
        
        return document_tree

    def _enrich_images_from_pdf(self, pdf_path: str, markdown_text: str) -> str:
        """Trích xuất ảnh từ PDF bằng PyMuPDF, gọi LLaVA phân tích, thay thế tại chỗ vào Markdown."""
        try:
            import fitz  # PyMuPDF
        except ImportError:
            logger.warning("[MarkItDownParser] PyMuPDF chưa được cài. Bỏ qua bước phân tích ảnh trong PDF.")
            return markdown_text
        
        # Tìm tất cả dòng ảnh trong Markdown
        image_pattern = re.compile(r'!\[([^\]]*)\]\(([^)]+)\)')
        image_matches = list(image_pattern.finditer(markdown_text))
        
        if not image_matches:
            logger.info("[MarkItDownParser] PDF không chứa ảnh nào. Bỏ qua.")
            return markdown_text
            
        # Trích xuất ảnh vật lý từ PDF theo thứ tự đọc (reading flow order) của trang
        temp_dir = tempfile.mkdtemp(prefix="pdf_images_")
        extracted_images = []
        
        try:
            doc = fitz.open(pdf_path)
            img_index = 0
            for page_num in range(len(doc)):
                page = doc[page_num]
                
                # Sử dụng get_text("dict") để lấy các block dạng ảnh (type 1) theo đúng thứ tự đọc (layout reading order - Bug 5)
                # Điều này giải quyết triệt để lỗi map nhầm ảnh trong các cấu trúc PDF phức tạp (như 2 cột hoặc có bảng biểu xen kẽ)
                text_dict = page.get_text("dict")
                page_images = [b for b in text_dict.get("blocks", []) if b.get("type") == 1]
                
                for img_block in page_images:
                    image_bytes = img_block.get("image")
                    image_ext = img_block.get("ext", "png")
                    if not image_bytes:
                        continue
                    try:
                        img_filename = f"pdf_img_{img_index}.{image_ext}"
                        img_path = os.path.join(temp_dir, img_filename)
                        
                        with open(img_path, "wb") as f:
                            f.write(image_bytes)
                        
                        extracted_images.append({
                            "path": img_path,
                            "page": page_num + 1,
                            "bbox": img_block.get("bbox"),
                            "index": img_index
                        })
                        img_index += 1
                    except Exception as e:
                        logger.warning(f"[MarkItDownParser] Không thể trích xuất ảnh từ image block ở trang {page_num + 1}: {e}")
            doc.close()
        except Exception as e:
            logger.error(f"[MarkItDownParser] Lỗi khi mở PDF bằng PyMuPDF: {e}")
            return markdown_text
            
        if not extracted_images:
            logger.info("[MarkItDownParser] PyMuPDF không tìm thấy ảnh nhúng nào trong PDF.")
            return markdown_text
            
        # Khởi tạo ImageParser để gọi LLaVA
        try:
            from .image_parser import ImageParser
            img_parser = ImageParser()
        except Exception as e:
            logger.error(f"[MarkItDownParser] Không thể khởi tạo ImageParser: {e}")
            return markdown_text
            
        # Ghép nối và thay thế theo thứ tự từ cuối lên đầu để không làm lệch vị trí (offset)
        enriched_markdown = markdown_text
        MAX_IMAGES = 10
        
        for i in range(len(image_matches) - 1, -1, -1):
            match = image_matches[i]
            alt_text = match.group(1) or "Hình ảnh"
            
            if i < len(extracted_images):
                img_info = extracted_images[i]
                
                # Chỉ phân tích tối đa 10 hình ảnh bằng LLaVA (Bug 4)
                if i < MAX_IMAGES:
                    description = img_parser._describe_with_llava(img_info["path"])
                    if description:
                        replacement = f"[Mô tả hình ảnh - {alt_text} (Trang {img_info['page']})]: {description}"
                        logger.info(f"[MarkItDownParser] Đã phân tích ảnh {i+1} bằng LLaVA.")
                    else:
                        replacement = f"[Hình ảnh: {alt_text} (Trang {img_info['page']})]"
                else:
                    replacement = f"[Hình ảnh: {alt_text} (Trang {img_info['page']})]"
            else:
                replacement = f"[Hình ảnh: {alt_text}]"
                
            enriched_markdown = (
                enriched_markdown[:match.start()] + 
                replacement + 
                enriched_markdown[match.end():]
            )
            
        # Dọn dẹp thư mục tạm
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
            
        return enriched_markdown

    def _enrich_base64_images(self, markdown_text: str) -> str:
        """Trích xuất ảnh Base64 (từ DOCX, PPTX), lưu tạm, gọi LLaVA phân tích, thay thế tại chỗ."""
        import base64
        
        # Biểu thức chính quy tìm ![alt](data:image/png;base64,...)
        image_pattern = re.compile(r'!\[([^\]]*)\]\(data:image/([^;]+);base64,([^)]+)\)')
        image_matches = list(image_pattern.finditer(markdown_text))
        
        if not image_matches:
            return markdown_text
            
        logger.info(f"[MarkItDownParser] Tìm thấy {len(image_matches)} ảnh Base64 nhúng. Đang xử lý bằng LLaVA...")
        
        try:
            from .image_parser import ImageParser
            img_parser = ImageParser()
        except Exception as e:
            logger.error(f"[MarkItDownParser] Không thể khởi tạo ImageParser: {e}")
            return markdown_text
            
        temp_dir = tempfile.mkdtemp(prefix="base64_images_")
        enriched_markdown = markdown_text
        
        # Xử lý từ cuối lên đầu để không làm lệch index thay thế
        MAX_IMAGES = 10
        for i in range(len(image_matches) - 1, -1, -1):
            match = image_matches[i]
            alt_text = match.group(1) or "Hình ảnh"
            img_ext = match.group(2)
            b64_data = match.group(3)
            
            # Chỉ xử lý LLaVA cho 10 ảnh đầu tiên (Bug 4) để tránh quá tải
            if i >= MAX_IMAGES:
                replacement = f"[Hình ảnh: {alt_text}]"
                enriched_markdown = (
                    enriched_markdown[:match.start()] + 
                    replacement + 
                    enriched_markdown[match.end():]
                )
                continue
                
            try:
                # Giải mã Base64
                img_bytes = base64.b64decode(b64_data)
                img_filename = f"img_{i}.{img_ext}"
                img_path = os.path.join(temp_dir, img_filename)
                
                with open(img_path, "wb") as f:
                    f.write(img_bytes)
                    
                # Gọi LLaVA phân tích ảnh
                description = img_parser._describe_with_llava(img_path)
                
                if description:
                    replacement = f"[Mô tả hình ảnh - {alt_text}]: {description}"
                    logger.info(f"[MarkItDownParser] Đã phân tích ảnh Base64 {i+1} bằng LLaVA.")
                else:
                    replacement = f"[Hình ảnh: {alt_text}]"
                    
                enriched_markdown = (
                    enriched_markdown[:match.start()] + 
                    replacement + 
                    enriched_markdown[match.end():]
                )
                    
            except Exception as e:
                logger.error(f"[MarkItDownParser] Lỗi khi xử lý ảnh Base64 {i+1}: {e}")
                
        # Dọn dẹp thư mục tạm
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
            
        return enriched_markdown
