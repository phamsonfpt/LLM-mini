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
        
        from ...utils.config import settings
        self.vision_mode = settings.vision_mode
        self.vision_model_name = settings.vision_model
        
        self.vision_model = None
        self.vision_tokenizer = None
        self.vision_processor = None

    def _image_to_base64(self, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def _describe_with_local_vision(self, image_path: str) -> Optional[str]:
        """Sử dụng Vision Model chạy Local (ví dụ: Moondream2) qua thư viện transformers."""
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            from PIL import Image

            # Khởi tạo model một lần duy nhất vào RAM/VRAM
            if self.vision_model is None:
                print(f"[ImageParser] Đang tải Native Vision Model ({self.vision_model_name}). Việc này có thể tốn vài phút ở lần đầu tiên...")
                device = "cuda" if torch.cuda.is_available() else "cpu"
                if platform.system() == "Darwin":
                    device = "mps" if torch.backends.mps.is_available() else "cpu"
                
                # Cấu hình cụ thể cho moondream2
                if "moondream2" in self.vision_model_name.lower():
                    self.vision_model = AutoModelForCausalLM.from_pretrained(
                        self.vision_model_name, trust_remote_code=True, revision="2024-08-26"
                    ).to(device)
                    self.vision_tokenizer = AutoTokenizer.from_pretrained(self.vision_model_name, revision="2024-08-26")
                else:
                    # Model khác tự nạp cơ bản (dự phòng)
                    self.vision_model = AutoModelForCausalLM.from_pretrained(self.vision_model_name, trust_remote_code=True).to(device)
                    self.vision_tokenizer = AutoTokenizer.from_pretrained(self.vision_model_name)
                    
            image = Image.open(image_path)
            
            if "moondream2" in self.vision_model_name.lower():
                enc_image = self.vision_model.encode_image(image)
                answer = self.vision_model.answer_question(enc_image, "Describe this image in detail and extract any text visible.", self.vision_tokenizer)
                return answer.strip()
            else:
                return "[ImageParser] Chưa hỗ trợ thư viện giao tiếp cho model này ngoài moondream2"
                
        except ImportError:
            print("[ImageParser] Thiếu thư viện transformers hoặc torch. Chạy OCR fallback.")
            return None
        except Exception as e:
            print(f"[ImageParser] Lỗi khi chạy Native Vision Model: {e}")
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

        # 1. Thử dùng LLaVA / Local Vision LLM
        description = None
        if self.vision_mode == "local_model":
            print(f"[ImageParser] Đang phân tích ảnh bằng Local Vision ({self.vision_model_name}): {os.path.basename(image_path)}")
            description = self._describe_with_local_vision(image_path)
        
        # 2. Nếu thất bại hoặc dùng chế độ OCR
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
