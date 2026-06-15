import os
import shutil
import re

base_dir = r"d:\LLM_mini"
src_dir = os.path.join(base_dir, "src")

# 1. Update DESIGN.md
design_path = os.path.join(base_dir, "DESIGN.md")
with open(design_path, "r", encoding="utf-8") as f:
    text = f.read()

new_tree = """```text
D:.
├── .dockerignore
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Dockerfile
├── flowchart TB.txt
├── parsing_trace_result.md
├── pipeline_a_demo.py
├── pipeline_viewer.html
├── README.md
├── requirements.txt
├── run_mac.command
├── run_windows.bat
├── test_llm.py
├── test_pipeline.py
├── test_stream.py
├── test_ui_stream.py
├── trace_metadata.py
├── update_html.py
├── [Description]-Building-Simple-NotebookLM.pdf
├── image/
├── metrics_test/
├── scratch/
├── pipeline_a_internals/      <-- THƯ MỤC TEST/PROTOTYPE: POC ban đầu
│   ├── 01_parse_and_metadata.py
│   ├── 02_chunking.py
│   ├── 03_tokenizing_and_bm25.py
│   ├── 04_embedding_and_qdrant.py
│   └── isolated_storage/
└── src/                       <-- CODEBASE CHÍNH THỨC (PRODUCTION)
    ├── __init__.py
    ├── cache.py
    ├── config.py
    ├── export.py
    ├── filters.py
    ├── learning.py
    ├── notebook_store.py
    ├── observability.py
    ├── rag.py
    ├── schemas.py
    ├── session.py
    ├── store.py
    ├── stream_batching.py
    ├── worker.py
    │
    ├── ingestion/               <-- MỚI: Quản lý toàn bộ luồng Ingestion
    │   ├── __init__.py
    │   ├── indexing.py
    │   └── parsers/             <-- MỚI: Xử lý các định dạng nguồn
    │       ├── __init__.py
    │       ├── pdf_parser.py
    │       ├── docx_pptx_parser.py
    │       ├── web_parser.py
    │       ├── youtube_parser.py
    │       ├── audio_parser.py
    │       ├── image_parser.py
    │       └── spreadsheet.py
    │
    ├── models/                  <-- MỚI: Tách biệt logic Model
    │   ├── __init__.py
    │   ├── llm.py               
    │   └── llm_gguf.py          
    │
    ├── evaluation/              <-- Đã có: Đánh giá chất lượng
    │   ├── __init__.py
    │   ├── benchmark_rag.csv
    │   ├── chunking_strategies.py
    │   ├── ragas_evaluator.py
    │   ├── run_chunking.py
    │   └── run_reranking.py
    │
    ├── interfaces/              <-- Đã có: Giao diện & API
    │   ├── __init__.py
    │   ├── api.py
    │   ├── cli.py
    │   ├── styles.py
    │   └── ui.py
    │
    ├── prompts/                 <-- Đã có: Quản lý template
    │   ├── answer.jinja2
    │   ├── flashcards.jinja2
    │   ├── quiz.jinja2
    │   ├── summary_map.jinja2
    │   ├── summary_reduce.jinja2
    │   └── summary_single.jinja2
    │
    └── retrieval/               <-- Đã có: Luồng truy vấn
        ├── __init__.py
        ├── bm25_index.py
        ├── context_builder.py
        ├── hybrid_search.py
        ├── reranker.py
        └── router.py
```"""

pattern = r'```text\nD:\..*?```'
text = re.sub(pattern, new_tree, text, flags=re.DOTALL)
with open(design_path, "w", encoding="utf-8") as f:
    f.write(text)

# 2. CREATE FOLDERS
os.makedirs(os.path.join(src_dir, "ingestion", "parsers"), exist_ok=True)
os.makedirs(os.path.join(src_dir, "models"), exist_ok=True)

# 3. MOVE FILES
def safe_move(src_name, dest_folder):
    s = os.path.join(src_dir, src_name)
    d = os.path.join(src_dir, dest_folder, src_name)
    if os.path.exists(s):
        shutil.move(s, d)

safe_move("llm.py", "models")
safe_move("llm_gguf.py", "models")
safe_move("indexing.py", "ingestion")
safe_move("bm25_index.py", "retrieval")

# 4. TOUCH NEW FILES
def touch(filepath):
    if not os.path.exists(filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('')

touch(os.path.join(src_dir, "ingestion", "__init__.py"))
touch(os.path.join(src_dir, "ingestion", "parsers", "__init__.py"))
touch(os.path.join(src_dir, "models", "__init__.py"))

parsers = [
    "pdf_parser.py", "docx_pptx_parser.py", "web_parser.py", 
    "youtube_parser.py", "audio_parser.py", "image_parser.py", "spreadsheet.py"
]
for p in parsers:
    touch(os.path.join(src_dir, "ingestion", "parsers", p))

print("Refactoring completed perfectly!")
