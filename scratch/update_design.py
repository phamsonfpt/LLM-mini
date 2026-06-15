import sys

file_path = r'd:\LLM_mini\DESIGN.md'

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the old explanation of directory structure with a mapped one
old_note = "## 📝 Chú thích các thành phần chính (Key Components)"

new_note = """### 16.2 Ánh Xạ Kiến Trúc Vào Cấu Trúc Code (Architecture-to-Codebase Mapping)

Để thấy rõ sự bổ trợ giữa **Thiết kế Logic (Kiến trúc)** và **Thiết kế Vật lý (Codebase)**, dưới đây là cách các thành phần trong hệ thống được ánh xạ vào thư mục mã nguồn:

1. **Ingestion Pipeline (Mục 4)** -> `pipeline_a_internals/`
   - `01_parse_and_metadata.py`: Đảm nhận việc Format Detection và Format-Specific Parser.
   - `02_chunking.py`: Triển khai Chunking Strategy (Mục 8).
   - `03_tokenizing_and_bm25.py`: Sinh Sparse Encoding (Mục 10).
   - `04_embedding_and_qdrant.py`: Sinh Dense Embedding và upsert vào Qdrant (Mục 9 & 11).

2. **Multimodal Model & LLaVA (Mục 3)** -> `src/llm.py` & `src/llm_gguf.py`
   - Giao tiếp với Ollama server, triển khai auto-detection phần cứng và quản lý local model (LLaVA/GGUF/Tesseract).

3. **Hybrid Search & Fusion (Mục 12 & 13)** -> `src/retrieval/`
   - `hybrid_search.py`: Kết hợp BM25 (Sparse) và Qdrant (Dense).
   - `reranker.py`: Cross-Encoder reranking các chunk sau khi lấy ra từ Hybrid Search.
   - `router.py`: Quyết định luồng query của user.

4. **Vector Database & Storage (Mục 11)** -> `isolated_storage/` & `src/store.py`
   - Cấu trúc thư mục `.lock`, `meta.json`, `storage.sqlite` mô phỏng local Qdrant collection và persistent store cho Document Tree.

5. **Query Pipeline & Output (Mục 14 & 15)** -> `src/interfaces/` & `src/rag.py`
   - `rag.py`: Điều phối luồng RAG từ lúc nhận query đến khi sinh Answer + Citation.
   - `api.py`, `ui.py`: Giao diện tương tác người dùng.

"""

if old_note in content:
    # We replace the old note and everything below it until the end of the section, 
    # but there might be Section 17 after it. Let's find Section 17.
    parts = content.split(old_note)
    
    # Check if section 17 is in the second part
    sec_17_header = "## 17."
    if sec_17_header in parts[1]:
        subparts = parts[1].split(sec_17_header, 1)
        new_content = parts[0] + new_note + "\n\n" + sec_17_header + subparts[1]
    else:
        new_content = parts[0] + new_note + "\n\n" + parts[1] # If there's no sec 17, just replace
else:
    # If not found, just append to the end of section 16
    sec_17_header = "## 17."
    if sec_17_header in content:
        parts = content.split(sec_17_header, 1)
        new_content = parts[0] + "\n\n" + new_note + "\n\n" + sec_17_header + parts[1]
    else:
        new_content = content + "\n\n" + new_note

pros_cons_section = """
---

## 18. Đánh Giá Kiến Trúc Tổng Thể (Pros & Cons)

Việc kết hợp giữa cấu trúc codebase module hóa và kiến trúc Local Multimodal RAG tạo ra một hệ thống RAG thu nhỏ (NotebookLM Clone) cực kỳ mạnh mẽ. Dưới đây là phân tích ưu nhược điểm:

### Ưu Điểm (Pros)

1. **Bảo mật tuyệt đối (100% Airgapped/Offline):**
   - Sự phụ thuộc vào Ollama (LLaVA / Qwen) và Qdrant Local giúp toàn bộ dữ liệu (tài liệu nội bộ, ảnh mât, query) không bao giờ rời khỏi thiết bị. Hoàn hảo cho Enterprise RAG hoặc các tổ chức yêu cầu bảo mật cao.
   
2. **Xử lý Đa phương thức (Multimodal) Thống nhất:**
   - Thay vì dùng pipeline OCR truyền thống rườm rà, kiến trúc dùng LLaVA làm "Vision Parser" giúp trích xuất không chỉ chữ mà còn là **ngữ nghĩa của biểu đồ, sơ đồ** một cách tự nhiên.

3. **Chất lượng truy xuất (Recall) cực cao:**
   - Cấu trúc kết hợp Hybrid Search (Dense + Sparse/BM25) và Reranker bảo đảm không sót thông tin từ khóa đặc thù (mã sản phẩm, tên riêng) lẫn thông tin ngữ nghĩa.

4. **Kiến trúc Code Modularity Tốt:**
   - Ingestion (trong `pipeline_a_internals`) được tách biệt hoàn toàn với Serving & Query (trong `src/`). Cấu trúc này giúp dễ dàng thay thế component (ví dụ: đổi Qdrant sang Milvus, hoặc thay đổi Chunking Strategy) mà không vỡ hệ thống.

### Nhược Điểm & Thách Thức (Cons & Limitations)

1. **Tiêu Tốn Tài Nguyên Phần Cứng (Hardware-Intensive):**
   - Chạy mô hình Multimodal (LLaVA 13B) và Embedding Model cùng lúc đòi hỏi máy tính có ít nhất 8GB - 12GB VRAM. 
   - Mặc dù kiến trúc có auto-detection (chuyển đổi qua GGUF/Quantization hoặc Tesseract khi thiếu VRAM), nhưng chất lượng sẽ bị suy giảm đáng kể trên phần cứng yếu.

2. **Nút Thắt Cổ Chai Ở Tốc Độ Ingestion:**
   - Việc xử lý Vision Offline rất chậm (2-5 giây/ảnh). Nếu đưa vào một PDF chứa 100 hình ảnh/biểu đồ, pipeline ingestion có thể mất vài phút đến hàng chục phút, không thể real-time như dùng API của GPT-4o.

3. **Khó Khăn Phân Tích Layout PDF Phức Tạp:**
   - Tài liệu PDF đa cột, chứa bảng biểu lồng nhau hoặc form phức tạp vẫn luôn là bài toán khó. Reading Order Model cần cực kỳ chính xác, nếu không Document Tree sẽ bị sai lệch cấu trúc trước khi kịp tới bước Markdown format.

4. **Quản Trị Vector Database RAM:**
   - Qdrant lưu trữ cả Sparse Vector có thể phình to rất nhanh về kích thước RAM so với các cấu trúc Inverted Index truyền thống, yêu cầu tối ưu hóa payload và quantization vectors nếu scale lên hàng triệu chunks.

**Kết luận:** Hệ thống là một thiết kế xuất sắc mang tính tiên phong cho **Local, Privacy-First RAG**, chấp nhận đánh đổi (trade-off) tốc độ xử lý ban đầu để lấy sự riêng tư và khả năng hiểu đa luồng nội dung (Multimodal) toàn diện.
"""

if "## 18. Đánh Giá" not in new_content:
    new_content += pros_cons_section

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Update complete!")
