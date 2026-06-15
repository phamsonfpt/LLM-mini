import sys

file_path = r'd:\LLM_mini\DESIGN.md'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

# Split out section 16
parts1 = text.split('## 16. Cấu Trúc Thư Mục Dự Án')
part1 = parts1[0]

# Extract Section 17 if it exists
part2 = ''
if '## 17. Tech Stack' in text:
    part2 = '## 17. Tech Stack' + text.split('## 17. Tech Stack')[1].split('## 18.')[0]

new_section_16 = """## 16. Cấu Trúc Thư Mục Dự Án (Hoàn Chỉnh)

Để đáp ứng được toàn bộ các tính năng kiến trúc được nêu ở các phần trên (bao gồm parsing nhiều định dạng: YouTube, Web, Audio, PDF, Local Vision Model, Hybrid Search...), cấu trúc thư mục của dự án cần được tái cấu trúc và mở rộng so với nguyên bản. Dưới đây là cấu trúc thư mục tổng quát và đầy đủ nhất:

```text
D:.
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── README.md
├── requirements.txt
├── run_windows.bat
├── test_pipeline.py
├── image/
├── metrics_test/
├── isolated_storage/
│   └── qdrant/
│       ├── .lock
│       ├── meta.json
│       └── collection/
├── src/
│   ├── main.py
│   ├── config.py
│   ├── schemas.py
│   ├── store.py
│   ├── observability.py
│   │
│   ├── ingestion/               <-- MỚI: Quản lý toàn bộ luồng Ingestion (Mục 4)
│   │   ├── __init__.py
│   │   ├── pipeline.py          <-- Orchestrator chính
│   │   ├── chunking.py          <-- Chunking Strategy (Mục 8)
│   │   ├── embedding.py         <-- Dense/Sparse Encoding (Mục 9, 10)
│   │   └── parsers/             <-- MỚI: Xử lý 13 định dạng nguồn
│   │       ├── __init__.py
│   │       ├── pdf_parser.py
│   │       ├── docx_pptx_parser.py
│   │       ├── web_parser.py    <-- Parse Website/HTML
│   │       ├── youtube_parser.py<-- Parse YouTube Transcript
│   │       ├── audio_parser.py  <-- Tích hợp Whisper offline
│   │       ├── image_parser.py  <-- Tích hợp LLaVA Vision
│   │       └── spreadsheet.py   <-- Excel / CSV
│   │
│   ├── models/                  <-- MỚI: Tách biệt logic quản lý Model (Mục 3)
│   │   ├── __init__.py
│   │   ├── vision_llm.py        <-- Local Vision (LLaVA/Ollama)
│   │   └── text_llm.py          <-- Generation LLM
│   │
│   ├── retrieval/               <-- Đã có: Luồng truy vấn (Mục 12, 13, 14)
│   │   ├── context_builder.py
│   │   ├── hybrid_search.py     <-- BM25 + Qdrant
│   │   ├── reranker.py          <-- Cross-Encoder
│   │   └── router.py
│   │
│   ├── interfaces/              <-- Đã có: Giao diện & API
│   │   ├── api.py
│   │   └── ui.py
│   │
│   ├── prompts/                 <-- Quản lý template (Mục 15)
│   │   └── system_prompts.jinja2
│   │
│   └── evaluation/              <-- Đánh giá chất lượng
│       └── ragas_evaluator.py
```

### Chú thích sự liên kết (Ánh xạ Kiến trúc - Codebase)

Sự kết hợp này giải quyết được vấn đề "Lý thuyết một đằng, Code một nẻo":
- **Mục 4 (Pipeline Ingestion đa định dạng)** giờ đây được hỗ trợ đầy đủ bởi package `src/ingestion/parsers/`. Mỗi loại file (YouTube, Audio, PDF) đều có một parser độc lập, tuân thủ nguyên tắc SOLID.
- **Mục 3 (Local Vision Model)** được module hóa vào `src/models/vision_llm.py`, chịu trách nhiệm auto-detect VRAM và gọi Ollama/LLaVA để xử lý ảnh từ `image_parser.py`.
- **Mục 9-13 (Retrieval & Qdrant)** được cấu trúc gọn gàng trong `src/retrieval/`, giao tiếp với `isolated_storage/qdrant/` trên ổ cứng.
"""

new_section_18 = """---

## 18. Đánh Giá Kiến Trúc Tổng Thể (Pros & Cons của Phiên bản Hoàn chỉnh)

Sự kết hợp giữa tài liệu Kiến trúc (DESIGN 1) và Cấu trúc Code (DESIGN gốc) tạo nên một bản thiết kế cấp Production. Việc mở rộng thư mục `src/ingestion/parsers/` để bao phủ toàn bộ 13 định dạng giúp hệ thống trở thành một "NotebookLM thực thụ".

### Ưu Điểm (Pros)
1. **Khả năng mở rộng (Extensibility) xuất sắc:** Bằng cách tách riêng thư mục `parsers/`, khi cần hỗ trợ định dạng mới (VD: ePub), chỉ cần viết thêm `epub_parser.py` mà không phải sửa lõi hệ thống.
2. **Bảo mật tuyệt đối (100% Offline/Airgapped):** Dùng LLaVA (Vision), Whisper (Audio) và Qdrant local giúp đảm bảo toàn bộ dữ liệu (tài liệu, âm thanh, hình ảnh) không bao giờ rời khỏi thiết bị.
3. **Chất lượng truy xuất (Recall) toàn diện:** Việc biến mọi nguồn dữ liệu (từ video YouTube đến file Excel) về cùng một định dạng **Document Tree -> Markdown Canonical** kết hợp Hybrid Search (Dense + Sparse/BM25) và Reranker bảo đảm AI có thể tìm và hiểu chéo thông tin giữa một video và một file PDF dễ dàng.
4. **Xử lý Đa phương thức (Multimodal) Thống nhất:** Thay vì dùng OCR truyền thống rườm rà, kiến trúc dùng LLaVA làm "Vision Parser" giúp trích xuất trực tiếp ngữ nghĩa của biểu đồ, sơ đồ.

### Nhược Điểm & Thách Thức (Cons & Limitations)
1. **Quản trị Dependency & Môi trường cực kì phức tạp:** Để chạy được Whisper (Audio), LLaVA (Vision), Youtube-Transcript-Api (YouTube), và Playwright (Web Parser) trong cùng một project offline sẽ khiến file `requirements.txt` và `Dockerfile` rất khổng lồ. Rủi ro xung đột thư viện CUDA/PyTorch là rất cao.
2. **Tiêu Tốn Tài Nguyên Phần Cứng (Hardware-Intensive):** Phải tải sẵn nhiều mô hình (Embedding model, Reranker model, LLaVA 13B, Whisper) vào RAM/VRAM. Yêu cầu thiết bị tốn ít nhất 12-16GB VRAM để chạy mượt mà tất cả các pipeline.
3. **Nút Thắt Tốc Độ ở Ingestion:** Xử lý Vision Offline (2-5 giây/ảnh) và Audio Offline (Whisper) rất chậm. Nếu ingest một video YouTube dài 2 tiếng và 1 PDF chứa 100 biểu đồ, hệ thống sẽ mất rất lâu mới index xong, khác xa tốc độ realtime của API cloud.
4. **Bảo trì Web/YouTube Parser:** Các trang web và YouTube thường xuyên thay đổi cấu trúc HTML hoặc cơ chế chống bot. Các parser nội bộ cần cập nhật liên tục nếu không sẽ hỏng (breaking changes).

**Kết luận:** Bản thiết kế hoàn chỉnh này biến dự án từ một "demo pipeline" nhỏ lẻ thành một **Nền tảng RAG Đa phương thức Cấp Doanh nghiệp**. Đổi lại, kỹ sư cần giải quyết triệt để bài toán tối ưu phần cứng và quản lý dependency bằng Docker.
"""

final_content = part1.strip() + '\n\n' + new_section_16.strip() + '\n\n' + part2.strip() + '\n\n' + new_section_18.strip() + '\n'

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(final_content)

print("Update successfully!")
