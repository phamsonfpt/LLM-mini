import os
import re

base_dir = r"d:\LLM_mini"
src_dir = os.path.join(base_dir, "src")
ingestion_dir = os.path.join(src_dir, "ingestion")
parsers_dir = os.path.join(ingestion_dir, "parsers")

# 1. DELETE THE OLD DUMB PARSERS
old_parsers = [
    "pdf_parser.py", "docx_pptx_parser.py", "web_parser.py", "spreadsheet.py"
]
for p in old_parsers:
    path = os.path.join(parsers_dir, p)
    if os.path.exists(path):
        os.remove(path)

# 2. CREATE THE NEW DIRECTORY STRUCTURE
layout_dir = os.path.join(ingestion_dir, "layout")
vision_dir = os.path.join(ingestion_dir, "vision")
os.makedirs(layout_dir, exist_ok=True)
os.makedirs(vision_dir, exist_ok=True)

# 3. TOUCH THE NEW FILES
def touch(filepath):
    if not os.path.exists(filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('')

# Root ingestion files
touch(os.path.join(ingestion_dir, "format_detector.py"))
touch(os.path.join(ingestion_dir, "document_tree.py"))
touch(os.path.join(ingestion_dir, "markdown_renderer.py"))

# Parsers
touch(os.path.join(parsers_dir, "markitdown_parser.py"))
touch(os.path.join(parsers_dir, "markdown_parser.py"))
touch(os.path.join(parsers_dir, "text_parser.py"))
# (youtube, audio, image already exist)

# Layout
touch(os.path.join(layout_dir, "__init__.py"))
touch(os.path.join(layout_dir, "reading_order.py"))
touch(os.path.join(layout_dir, "semantic_classifier.py"))
touch(os.path.join(layout_dir, "relationship_builder.py"))

# Vision
touch(os.path.join(vision_dir, "__init__.py"))
touch(os.path.join(vision_dir, "local_vision_model.py"))
touch(os.path.join(vision_dir, "tesseract_ocr.py"))
touch(os.path.join(vision_dir, "vision_pipeline.py"))

# 4. UPDATE DESIGN.md
design_path = os.path.join(base_dir, "DESIGN.md")
with open(design_path, "r", encoding="utf-8") as f:
    text = f.read()

# Define the new tree snippet
old_ingestion_snippet = r"    ├── ingestion/.*?    ├── models/"
new_ingestion_snippet = """    ├── ingestion/
    │   ├── __init__.py
    │   ├── format_detector.py      <-- Nhận file -> trả về format type
    │   ├── document_tree.py        <-- Document Tree Builder
    │   ├── markdown_renderer.py    <-- Document Tree -> Markdown
    │   ├── indexing.py
    │   ├── parsers/
    │   │   ├── __init__.py
    │   │   ├── markitdown_parser.py<-- Universal Parser: PDF, DOCX, PPTX, HTML, Excel -> MD
    │   │   ├── markdown_parser.py  <-- Parse file MD -> Document Tree
    │   │   ├── youtube_parser.py   <-- YouTube URL -> Document Tree
    │   │   ├── audio_parser.py     <-- Audio -> Transcript -> Document Tree
    │   │   ├── image_parser.py     <-- Image -> OCR + Vision -> Document Tree
    │   │   └── text_parser.py      <-- TXT / Copy-Paste -> Document Tree
    │   ├── layout/
    │   │   ├── __init__.py
    │   │   ├── reading_order.py    <-- Sắp xếp reading order
    │   │   ├── semantic_classifier.py<-- Phân loại title/heading/paragraph...
    │   │   └── relationship_builder.py<-- Ghép caption với figure/table
    │   └── vision/
    │       ├── __init__.py
    │       ├── local_vision_model.py<-- LLaVA + Ollama
    │       ├── tesseract_ocr.py    <-- Fallback OCR
    │       └── vision_pipeline.py  <-- Hybrid strategy
    │
    ├── models/"""

text = re.sub(old_ingestion_snippet, new_ingestion_snippet, text, flags=re.DOTALL)

with open(design_path, "w", encoding="utf-8") as f:
    f.write(text)

print("Ingestion folder aligned successfully!")
