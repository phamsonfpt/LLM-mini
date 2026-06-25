# 📓 NotebookLM-Mini (Optimized Local RAG Edition)

NotebookLM-Mini là một trợ lý học tập cá nhân bảo mật cao chạy **100% Offline (Airgapped)** dựa trên kiến trúc **Retrieval-Augmented Generation (RAG)**. 

Ở phiên bản mới nhất, hệ thống đã được tối ưu hóa cực hạn để chạy mượt mà trên **MacBook Pro M2 (RAM 8GB / macOS)** bằng cách loại bỏ ảo hóa Docker cồng kềnh, chuyển sang sử dụng kiến trúc **Native Local (llama.cpp/Ollama + FastAPI + React)**. Nhờ đó tận dụng được 100% sức mạnh chip đồ họa **Apple Silicon GPU (Metal Acceleration)** với mức tiêu thụ RAM cực thấp.

Dự án hỗ trợ tải lên đa phương tiện cá nhân (PDF, DOCX, CSV, TXT, Markdown, Hình ảnh, Âm thanh, YouTube/Website URL...), tự động phân tích và tương tác qua:
* 💬 **Hỏi đáp siêu tốc (Streaming Chat):** Tìm kiếm lai lai (Hybrid Search: Vector + BM25) kết hợp Reranker & Nén ngữ cảnh chéo.
* 📝 **Cẩm nang học tập (Study Guide):** Tự động sinh tóm tắt, FAQ, thuật ngữ (Glossary) và sơ đồ tư duy (Mindmap).
* 🎯 **Học chủ động:** Tự động tạo Quiz trắc nghiệm và thẻ từ vựng (Flashcards).
* 🎙️ **Podcast tự động:** Chuyển đổi lời thoại tóm tắt tài liệu thành âm thanh giao tiếp giữa 2 MC (Text-to-Speech hỗ trợ cả offline và online).

---

## 🌟 Các Cải Tiến Tối Ưu Hóa Cho MacBook M2 8GB RAM

Hệ thống đã được tinh chỉnh mã nguồn để hoạt động mượt mà trên máy Mac RAM 8GB mà không gây nóng máy hoặc tràn RAM:
1. **🚀 Loại bỏ reload Reranker liên tục:** Mô hình Reranker (`CrossEncoder`) giờ đây được nạp và quản lý tập trung thông qua `VRAMOrchestrator` thay vì bị tải lại từ SSD mỗi lần Rerank/Compress.
2. **🧠 Cơ chế Coexistence:** Hệ thống tự động giữ cả mô hình nhúng (`vietnamese-sbert`) và reranker (`mMiniLMv2`) trên RAM chạy song song trong suốt quá trình truy xuất (Retrieval) thay vì nạp/xả liên tiếp, tăng tốc độ tìm kiếm tài liệu lên **gấp 5 lần** (latency < 1.2s).
3. **⚡ Bỏ qua Query Rewriting mặc định:** Tắt mặc định tính năng viết lại câu hỏi bằng LLM giúp tiết kiệm 1.5 - 3 giây chờ đợi cho mỗi câu chat (có thể bật lại trong file `.env` nếu cần).
4. **👁️ Tự động co giãn mô hình (Model Zoo Autotuning):** Khi phát hiện RAM 8GB, hệ thống tự chọn **moondream2 (1.6B)** cho Vision và **Whisper Base** cho Audio để tối giản bộ nhớ sử dụng, ngăn chặn tràn RAM vật lý gây swap ổ đĩa.
5. **📁 Tránh Eager Loading:** CSDL khởi động tức thì nhờ cơ chế phân tích kích thước Vector tĩnh thay vì nạp mô hình nhúng lên chạy thử.

---

## 📖 HƯỚNG DẪN CÀI ĐẶT VÀ SỬ DỤNG

### 1. Yêu cầu hệ thống ban đầu
* Hệ điều hành: **macOS (Apple Silicon M1/M2/M3/M4)**.
* Đã cài đặt **Python 3.10+** và **Node.js (v18+)** kèm **npm**.
* Khuyên dùng **Ollama** cài sẵn trên máy (chạy nền để tăng tốc GPU nhanh nhất).

### 2. Khởi động nhanh (1-Click Startup)

1. Mở Terminal tại thư mục gốc của dự án.
2. Cấp quyền thực thi và chạy file khởi động:
   ```bash
   chmod +x run_mac.command
   ./run_mac.command
   ```
3. Hệ thống sẽ tự động thực hiện:
   * Quét cấu hình phần cứng để cấu hình tệp `.env` tối ưu.
   * Tạo môi trường ảo Python (`.venv`) bằng trình quản lý gói siêu tốc `uv`.
   * Tải trước mô hình nhúng (`vietnamese-sbert`) và Reranker (`mMiniLMv2`) về ổ đĩa.
   * Khởi chạy LLM local (Ưu tiên kết nối qua Ollama `qwen2.5:3b` có sẵn, nếu không có sẽ tự tải llama-server chạy trực tiếp).
   * Mở trình duyệt Web tại địa chỉ: `http://127.0.0.1:8000`.

---

## 🛠️ HƯỚNG DẪN DÀNH CHO LẬP TRÌNH VIÊN (Developer)

Dự án được phân tách rõ ràng thành hai phần:

### 1. Frontend (React + Vite)
Nằm trong thư mục `frontend/`. 
* **Cài đặt thư viện:**
  ```bash
  cd frontend
  npm install
  ```
* **Chạy môi trường phát triển (Hot reload):**
  ```bash
  npm run dev
  ```
  *(Mở tại cổng http://localhost:5173)*
* **Đóng gói biên dịch (Build sản phẩm):**
  ```bash
  npm run build
  ```
  *Lưu ý:* Bản build sẽ nằm trong `frontend/dist`. Khi backend FastAPI khởi chạy, nó sẽ tự động phục vụ các file tĩnh này tại cổng `8000`, do đó bạn không cần bật dev server của frontend ở chế độ Production.

### 2. Backend (FastAPI)
Nằm trong thư mục `src/`.
* **Cấu hình môi trường:** Các thông số mô hình và cổng kết nối được quản lý tại file `.env` ở thư mục gốc:
  ```env
  RAG_EMBEDDING_MODEL=keepitreal/vietnamese-sbert
  RAG_RERANKER_MODEL=cross-encoder/mmarco-mMiniLMv2-L12-H384-v1
  RAG_VISION_MODE=ollama
  RAG_VISION_MODEL=moondream
  RAG_AUDIO_MODEL=base
  RAG_LLM_PROVIDER=ollama
  RAG_OLLAMA_MODEL=qwen2.5:3b
  RAG_llama_server_url=http://127.0.0.1:8080
  RAG_USE_QUERY_REWRITER=false
  ```
* **CSDL SQLite:** Lưu trữ lịch sử tại `storage/notebooks.db`.
* **CSDL Qdrant:** Lưu trữ cơ sở dữ liệu Vector tại thư mục `storage/qdrant/`.

---
*Dự án NotebookLM-Mini - Tối ưu hóa cực hạn, vận hành trơn tru.*
