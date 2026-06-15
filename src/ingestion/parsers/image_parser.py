import os
import base64
import requests
import json
from typing import Optional
from PIL import Image

from ..document_tree import DocumentNode, ImageNode, ParagraphNode

class ImageParser:
    """Parser xử lý hình ảnh sử dụng LLaVA (Ollama) và OCR (Tesseract) fallback."""

    def __init__(self, ollama_url: str = "http://localhost:11434", llava_model: str = "llava"):
        self.ollama_url = ollama_url
        self.llava_model = llava_model

    def _image_to_base64(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def _describe_with_llava(self, image_path: str) -> Optional[str]:
        """Gọi Ollama API với model LLaVA để phân tích ảnh."""
        try:
            base64_image = self._image_to_base64(image_path)
            prompt = "Please describe this image in detail. Extract any text visible. If it is a chart, explain the trends."
            
            payload = {
                "model": self.llava_model,
                "prompt": prompt,
                "images": [base64_image],
                "stream": False
            }
            
            response = requests.post(f"{self.ollama_url}/api/generate", json=payload, timeout=60)
            if response.status_code == 200:
                result = response.json()
                return result.get("response", "").strip()
            else:
                print(f"[ImageParser] LLaVA API lỗi {response.status_code}: {response.text}")
                return None
        except requests.exceptions.RequestException as e:
            print(f"[ImageParser] Không kết nối được với Ollama LLaVA: {e}")
            return None
        except Exception as e:
            print(f"[ImageParser] Lỗi khi chạy LLaVA: {e}")
            return None

    def _extract_text_with_ocr(self, image_path: str) -> Optional[str]:
        """Sử dụng Tesseract OCR để trích xuất chữ (Fallback)."""
        try:
            import pytesseract
            img = Image.open(image_path)
            text = pytesseract.image_to_string(img, lang='vie+eng')
            return text.strip()
        except Exception as e:
            print(f"[ImageParser] Lỗi OCR (Tesseract): {e}")
            return None

    def parse(self, image_path: str, source_metadata: Optional[dict] = None) -> DocumentNode:
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Không tìm thấy file ảnh: {image_path}")

        # Xây dựng metadata
        meta = source_metadata or {}
        meta["source_file"] = os.path.basename(image_path)
        meta["parser"] = "ImageParser"

        # 1. Thử dùng LLaVA (Vision LLM)
        print(f"[ImageParser] Đang phân tích ảnh bằng LLaVA: {os.path.basename(image_path)}")
        description = self._describe_with_llava(image_path)
        
        # 2. Nếu LLaVA thất bại, dùng OCR
        if not description:
            print("[ImageParser] Chuyển sang OCR Fallback (Tesseract)...")
            description = self._extract_text_with_ocr(image_path)
            if description:
                description = "OCR Trích xuất văn bản:\n" + description

        if not description:
            description = "[Không thể phân tích ảnh hoặc ảnh không có nội dung văn bản]"

        # Khởi tạo Document Tree
        doc_node = DocumentNode(metadata=meta)
        
        # Tạo ImageNode (có chứa text mô tả)
        img_node = ImageNode(
            alt_text=os.path.basename(image_path),
            url=f"file://{os.path.abspath(image_path)}",
            description=description,
            metadata={"description_source": "llava" if "OCR" not in description else "ocr"}
        )
        
        # Đưa đoạn văn bản vào dưới ImageNode để Chunking xử lý dễ hơn
        img_node.add_child(ParagraphNode(content=description))
        
        doc_node.add_child(img_node)
        
        return doc_node
