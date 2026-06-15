"""
Streamlit Web UI — Tầng Giao diện Multi-Workspace (Notebooks)
Mô phỏng trải nghiệm Google NotebookLM.
"""
import streamlit as st
import httpx
import json
import uuid
import sys
import os

# Đảm bảo Python nhận diện được thư mục gốc của dự án để import 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.config import settings
from src.interfaces.styles import GLOBAL_CSS

_API = settings.api_url

def _get_session_id():
    """Get or create a persistent session ID for this browser session."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())[:8]
    return st.session_state.session_id

def _api(method: str, path: str, **kwargs):
    try:
        res = httpx.request(method, f"{_API}{path}", timeout=180.0, **kwargs)
        if res.status_code >= 400:
            try:
                detail = res.json().get("detail", res.text)
            except Exception:
                detail = res.text

            if "API key required" in detail or "API_KEY" in detail or "API key not valid" in detail:
                st.error("🔑 **Lỗi cấu hình API Key:** Vui lòng kiểm tra file `.env`.")
            else:
                st.error(f"❌ **Lỗi từ Backend:** {detail}")
            return None
        return res.json()
    except Exception as e:
        st.error(f"Lỗi kết nối đến API backend: {e}")
        return None

def _state_key(*parts):
    return "::".join(str(part) for part in parts)

def _clear_state_prefix(prefix: str):
    for key in list(st.session_state.keys()):
        if str(key).startswith(prefix):
            del st.session_state[key]

def _render_citations(citations):
    if not citations:
        return
    with st.expander("📚 Nguồn trích dẫn (Citations)"):
        for c in citations:
            st.markdown(
                f"<span class='source-tag'>{c['source_marker']}</span> "
                f"<b>{c['filename']}</b> (Trang {c['page']})",
                unsafe_allow_html=True,
            )

def _has_learning_items(data: dict | None, key: str) -> bool:
    return bool(data and data.get(key))

def _api_stream(path: str, payload: dict, metadata_sink: dict | None = None):
    """Call streaming API and yield text chunks."""
    try:
        with httpx.stream("POST", f"{_API}{path}", json=payload, timeout=180.0) as response:
            if response.status_code != 200:
                response.read()
                try:
                    error_data = response.json()
                    detail = error_data.get("detail", response.text)
                except Exception:
                    detail = response.text
                yield f"\n\n⚠️ Lỗi hệ thống ({response.status_code}): {detail}"
                return

            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if "text" in data:
                        yield data["text"]
                    if data.get("done"):
                        if metadata_sink is not None:
                            metadata_sink.update({
                                "citations": data.get("citations", []),
                                "chunks": data.get("chunks", []),
                            })
                        break
    except Exception as e:
        yield f"\n\n⚠️ Lỗi kết nối đến Backend: {e}"

# -----------------------------------------------------------------------------
# Trạng thái hệ thống (State Machine)
# -----------------------------------------------------------------------------
# pages: "landing", "dashboard", "notebook"

if "page" not in st.session_state:
    st.session_state.page = "landing"
if "notebook_id" not in st.session_state:
    st.session_state.notebook_id = None
if "notebook_name" not in st.session_state:
    st.session_state.notebook_name = None

def navigate_to(page: str, notebook_id: str = None, notebook_name: str = None):
    st.session_state.page = page
    if notebook_id:
        st.session_state.notebook_id = notebook_id
    if notebook_name:
        st.session_state.notebook_name = notebook_name
    st.rerun()

# -----------------------------------------------------------------------------
# Trang 1: Landing Page
# -----------------------------------------------------------------------------
def render_landing():
    st.markdown(
        """
        <div style='text-align:center; padding-top: 100px;'>
            <h1 style='font-size: 4rem; font-family: Space Grotesk; color: #818cf8;'>NotebookLM</h1>
            <p style='font-size: 1.2rem; color: #94a3b8;'>Hệ thống RAG hỗ trợ học tập và nghiên cứu thông minh của riêng bạn.</p>
            <br>
        </div>
        """,
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("Dùng thử NotebookLM", use_container_width=True, type="primary"):
            navigate_to("dashboard")

# -----------------------------------------------------------------------------
# Trang 2: Dashboard (Danh sách Thẻ / Notebooks)
# -----------------------------------------------------------------------------
def render_dashboard():
    st.markdown("<h1 style='font-family: Space Grotesk; color: #818cf8;'>📓 Thẻ của tôi (Notebooks)</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8;'>Tạo thẻ mới hoặc chọn một thẻ đã có để tiếp tục làm việc.</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        new_name = st.text_input("Tên Thẻ Mới", placeholder="Nhập tên thẻ... (VD: Lịch sử, AI Research...)")
    
    st.markdown("**Chọn AI Backend cho thẻ này:**")
    provider_options = {
        "🖥️ Universal Local AI (Riêng tư, 100% tự động tương thích mọi phần cứng)": "hf_local",
        "🌐 Gemini API (Nhanh, cần API Key — ⚠️ không dùng với data riêng tư)": "gemini"
    }
    selected_provider_label = st.selectbox(
        "LLM Backend",
        list(provider_options.keys()),
        label_visibility="collapsed",
    )
    selected_provider = provider_options[selected_provider_label]
    if selected_provider == "gemini":
        st.warning("⚠️ **Lưu ý:** Gemini API sẽ gửi nội dung tài liệu của bạn lên máy chủ Google. Không nên dùng với dữ liệu riêng tư/nhạy cảm.")

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Tạo Thẻ Mới", use_container_width=True):
            if new_name.strip():
                with st.spinner("Đang tạo thẻ..."):
                    res = _api("POST", "/notebooks", json={"name": new_name.strip(), "llm_provider": selected_provider})
                    if res:
                        navigate_to("notebook", res["id"], res["name"])
            else:
                st.warning("Vui lòng nhập tên thẻ.")

    st.markdown("---")
    
    notebooks = _api("GET", "/notebooks")
    if not notebooks:
        st.info("Bạn chưa có Thẻ nào. Hãy tạo Thẻ mới ở trên.")
        return

    # Hiển thị dạng Grid
    cols = st.columns(3)
    for idx, nb in enumerate(notebooks):
        with cols[idx % 3]:
            provider_badge = {
                "gemini": "🌐 Gemini API",
                "hf_local": "🖥️ Local HF",
                "vllm": "⚡ vLLM",
            }.get(nb.get("llm_provider", "gemini"), "🌐 Gemini API")
            st.markdown(
                f"""
                <div class='glass-card' style='height: 120px; cursor: pointer; margin-bottom: 10px;'>
                    <h3 style='margin-bottom:0; color:#818cf8;'>{nb['name']}</h3>
                    <p style='font-size: 0.8rem; color: #94a3b8;'>{len(nb['documents'])} tài liệu</p>
                    <p style='font-size: 0.75rem; color: #6366f1; margin:0;'>AI: {provider_badge}</p>
                </div>
                """,
                unsafe_allow_html=True
            )
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Mở 📂", key=f"open_{nb['id']}", use_container_width=True):
                    with st.spinner("Đang mở thẻ..."):
                        navigate_to("notebook", nb["id"], nb["name"])
            with c2:
                if st.button("Xóa 🗑️", key=f"del_{nb['id']}", use_container_width=True):
                    _api("DELETE", f"/notebooks/{nb['id']}")
                    st.rerun()

# -----------------------------------------------------------------------------
# Trang 3: Notebook View (Trong một thẻ cụ thể)
# -----------------------------------------------------------------------------
def _sidebar_notebook(notebook_id: str, notebook_name: str):
    if st.sidebar.button("⬅️ Trở về Dashboard"):
        navigate_to("dashboard")
        
    st.sidebar.markdown(f"<h2 style='font-family:Space Grotesk; font-weight:700; color:#818cf8;'>📓 {notebook_name}</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("---")

    # Upload
    uploaded_file = st.sidebar.file_uploader(
        "Kéo thả tài liệu vào đây (Tự động nạp)",
        type=["pdf", "docx", "pptx", "xlsx", "csv", "html", "md", "txt", "jpg", "jpeg", "png"],
    )

    # Fetch notebook info to check LLM provider
    nb_list = _api("GET", "/notebooks")
    nb_data = next((n for n in (nb_list or []) if n["id"] == notebook_id), None)
    is_gemini = nb_data and nb_data.get("llm_provider") == "gemini"

    # Privacy selection
    if is_gemini:
        privacy_choice = st.sidebar.radio(
            "Nhãn bảo mật tài liệu:",
            ["🌍 Công khai (Public)", "🔒 Riêng tư (Private)"],
            index=0,
            help="Private: cảnh báo nếu notebook dùng Gemini API (gửi data lên cloud)",
        )
        privacy = "private" if "Private" in privacy_choice else "public"
    else:
        st.sidebar.success("🔒 **100% Local AI**\nDữ liệu không bao giờ rời khỏi máy tính.")
        privacy = "private"  # Always private for local models

    if uploaded_file is not None:
        uploaded_file_id = getattr(uploaded_file, "file_id", None)
        if not uploaded_file_id:
            uploaded_file_size = getattr(uploaded_file, "size", None)
            if uploaded_file_size is None:
                uploaded_file_size = len(uploaded_file.getvalue())
            uploaded_file_id = f"{uploaded_file.name}:{uploaded_file_size}"
        if st.session_state.get("last_uploaded_file_id") != uploaded_file_id:
            st.session_state["last_uploaded_file_id"] = uploaded_file_id

            if privacy == "private" and is_gemini:
                st.sidebar.warning(
                    "⚠️ **Cảnh báo Bảo mật:** Thẻ này đang dùng **Gemini API** (cloud).\n\n"
                    "Tài liệu **Riêng tư** của bạn sẽ được gửi đến máy chủ Google để xử lý.\n\n"
                    "Vui lòng chọn một trong các tuỳ chọn bên dưới:"
                )
                confirmed = st.sidebar.checkbox("✅ Tôi hiểu rủi ro và vẫn muốn tiếp tục với Gemini API", key="privacy_confirm")

                if not confirmed:
                    st.sidebar.markdown("**Hoặc chuyển sang Local AI để bảo vệ dữ liệu:**")
                    col_a, col_b = st.sidebar.columns(2)
                    with col_a:
                        if st.button("🖥️ Dùng Local HF", key="switch_hf", use_container_width=True):
                            _api("POST", f"/notebooks/{notebook_id}/provider", json={"llm_provider": "hf_local"})
                            st.session_state["last_uploaded_file_id"] = None  # reset để upload lại
                            st.sidebar.success("✅ Đã chuyển sang Local HF! Hãy tải file lại.")
                            st.rerun()
                    with col_b:
                        if st.button("⚡ Dùng vLLM", key="switch_vllm", use_container_width=True):
                            _api("POST", f"/notebooks/{notebook_id}/provider", json={"llm_provider": "vllm"})
                            st.session_state["last_uploaded_file_id"] = None
                            st.sidebar.success("✅ Đã chuyển sang vLLM! Hãy tải file lại.")
                            st.rerun()
                    st.stop()

            with st.spinner("Đang xử lý và nhúng Vector, vui lòng đợi..."):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/octet-stream")}
                res = _api("POST", f"/upload/{notebook_id}", files=files, params={"privacy": privacy})
                if res:
                    task_id = res.get("task_id", "")
                    if task_id:
                        import time
                        while True:
                            status = _api("GET", f"/upload/status/{task_id}")
                            if not status or status.get("status") in ("done", "error"):
                                break
                            time.sleep(1.0)
                        
                        if status and status.get("status") == "done":
                            st.sidebar.success(f"✅ Đã nạp xong: {status.get('filename')}")
                        elif status and status.get("status") == "error":
                            st.sidebar.error(f"❌ Lỗi: {status.get('error_message')}")
                        
                        st.rerun()



    st.sidebar.markdown("---")
    
    # Document List
    st.sidebar.markdown("### Nguồn (Tài liệu đã nạp)")
    docs = _api("GET", f"/notebooks/{notebook_id}/documents")
    
    if not docs:
        st.sidebar.warning("Thẻ này chưa có tài liệu. Vui lòng tải lên.")
        return None, None

    for d in docs:
        col1, col2 = st.sidebar.columns([4, 1])
        with col1:
            st.markdown(f"📄 **{d['filename']}**", unsafe_allow_html=True)
        with col2:
            if st.button("🗑️", key=f"del_doc_{d['filename']}", help="Xóa tài liệu"):
                _api("DELETE", f"/notebooks/{notebook_id}/documents/{d['filename']}")
                st.rerun()
                
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔍 Bộ lọc tìm kiếm")
    doc_options = ["Toàn bộ tài liệu (Corpus)"] + [d["filename"] for d in docs]
    selected_doc = st.sidebar.selectbox("Chỉ định tài liệu", doc_options)
    doc_target = None if selected_doc == "Toàn bộ tài liệu (Corpus)" else selected_doc
    
    page_filter = None
    if doc_target:
        # We don't have page count in the simplified Notebook metadata yet, so fallback to simple text input or no filter
        st.sidebar.caption(f"Lọc theo tài liệu: {doc_target}")

    return doc_target, page_filter


@st.fragment
def _tab_chat(notebook_id, selected_doc, page_filter):
    st.markdown("<h2 style='font-family:Space Grotesk; font-weight:700;'>💬 Hỏi đáp với tài liệu</h2>", unsafe_allow_html=True)
    
    session_key = f"messages_{notebook_id}"
    if session_key not in st.session_state:
        nb_list = _api("GET", "/notebooks")
        nb_data = next((n for n in (nb_list or []) if n["id"] == notebook_id), None)
        st.session_state[session_key] = nb_data.get("messages", []) if nb_data else []

    use_streaming = st.checkbox("🚀 Streaming mode (SSE)", value=True)

    if st.button("Xóa lịch sử chat", type="secondary"):
        st.session_state[session_key] = []
        _api("DELETE", f"/notebooks/{notebook_id}/messages")
        st.rerun()

    for msg in st.session_state[session_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("citations"):
                _render_citations(msg["citations"])

    query = st.chat_input("Nhập câu hỏi của bạn về tài liệu ở đây...")
    if query:
        with st.chat_message("user"):
            st.markdown(query)
        msg_user = {"role": "user", "content": query}
        st.session_state[session_key].append(msg_user)
        _api("POST", f"/notebooks/{notebook_id}/messages", json=msg_user)

        filters = {"notebook_id": notebook_id}
        if page_filter:
            filters["page"] = page_filter
        if selected_doc:
            filters["filename"] = selected_doc

        with st.chat_message("assistant"):
            if use_streaming:
                payload = {
                    "question": query,
                    "k": settings.top_k,
                    "filters": filters,
                    "session_id": _get_session_id(),
                }
                response_placeholder = st.empty()
                collected = []
                stream_meta = {}
                for chunk in _api_stream("/ask/stream", payload, metadata_sink=stream_meta):
                    collected.append(chunk)
                    response_placeholder.markdown("".join(collected))

                full_answer = "".join(collected)
                citations = stream_meta.get("citations", [])
                _render_citations(citations)
                msg_asst = {
                    "role": "assistant",
                    "content": full_answer,
                    "citations": citations,
                }
                st.session_state[session_key].append(msg_asst)
                _api("POST", f"/notebooks/{notebook_id}/messages", json=msg_asst)
            else:
                with st.spinner("Đang suy nghĩ và trích xuất nguồn..."):
                    payload = {
                        "question": query,
                        "k": settings.top_k,
                        "filters": filters,
                        "session_id": _get_session_id(),
                    }
                    res = _api("POST", "/ask", json=payload)
                    if res:
                        st.markdown(res["answer"])
                        _render_citations(res["citations"])

                        msg_asst = {
                            "role": "assistant",
                            "content": res["answer"],
                            "citations": res["citations"]
                        }
                        st.session_state[session_key].append(msg_asst)
                        _api("POST", f"/notebooks/{notebook_id}/messages", json=msg_asst)


@st.fragment
def _tab_summary(notebook_id, selected_doc, page_filter):
    doc_key = selected_doc or "all"
    summary_key = _state_key("active_summary", notebook_id, doc_key)
    st.markdown("<h2 style='font-family:Space Grotesk; font-weight:700;'>📝 Hướng dẫn học tập (Study Guide)</h2>", unsafe_allow_html=True)
    summary_focus = st.text_input("Trọng tâm tóm tắt (Để trống để tóm tắt toàn bộ tài liệu)", placeholder="Ví dụ: các khái niệm cốt lõi...")
    
    # Auto-load from NotebookStore
    if summary_key not in st.session_state:
        nb_res = _api("GET", f"/notebooks/{notebook_id}")
        if nb_res and "learning_data" in nb_res:
            saved_data = nb_res["learning_data"].get("summary", {}).get(doc_key)
            if saved_data:
                st.session_state[summary_key] = saved_data

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("Tạo Hướng dẫn", key=f"btn_create_sum_{notebook_id}_{doc_key}"):
            with st.spinner("Đang phân tích..."):
                filters = {"notebook_id": notebook_id}
                if page_filter:
                    filters["page"] = page_filter

                payload = {
                    "document": selected_doc,
                    "query": summary_focus if summary_focus.strip() else None,
                    "filters": filters
                }
                res = _api("POST", "/summarize", json=payload)
                if res:
                    st.session_state[summary_key] = res
    with col_btn2:
        if summary_key in st.session_state:
            if st.button("🗑️ Xóa bài tập này", type="primary", key=f"btn_del_sum_{notebook_id}_{doc_key}"):
                _api("DELETE", f"/notebooks/{notebook_id}/learning/summary", params={"document": doc_key})
                del st.session_state[summary_key]
                st.rerun()

    if summary_key in st.session_state:
        sum_data = st.session_state[summary_key]
        st.markdown(f"""
        <div class='glass-card'>
            <h3 style='color:#818cf8;'>✨ Bản tóm tắt chính</h3>
            <div>{sum_data["summary"]}</div>
        </div>
        """, unsafe_allow_html=True)
        
        key_points_html = "".join(f"<li>{kp}</li>" for kp in sum_data["key_points"])
        st.markdown(f"""
        <div class='glass-card'>
            <h3 style='color:#818cf8;'>📌 Các ý chính nổi bật</h3>
            <ul style='margin-bottom:0; padding-left: 20px;'>
                {key_points_html}
            </ul>
        </div>
        """, unsafe_allow_html=True)


@st.fragment
def _tab_quiz(notebook_id, selected_doc, page_filter):
    doc_key = selected_doc or "all"
    quiz_key = _state_key("active_quiz", notebook_id, doc_key)
    answers_key = _state_key("quiz_answers", notebook_id, doc_key)
    submitted_key = _state_key("quiz_submitted", notebook_id, doc_key)
    option_prefix = _state_key("quiz_option", notebook_id, doc_key) + "::"
    st.markdown("<h2 style='font-family:Space Grotesk; font-weight:700;'>📝 Trắc nghiệm</h2>", unsafe_allow_html=True)
    count = st.slider("Số lượng câu", 3, 15, 5, key=f"sld_quiz_count_{notebook_id}_{doc_key}")

    # Auto-load from NotebookStore
    if quiz_key not in st.session_state:
        nb_res = _api("GET", f"/notebooks/{notebook_id}")
        if nb_res and "learning_data" in nb_res:
            saved_data = nb_res["learning_data"].get("quiz", {}).get(doc_key)
            if _has_learning_items(saved_data, "items"):
                st.session_state[quiz_key] = saved_data
                st.session_state[answers_key] = {}
                st.session_state[submitted_key] = False

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("Tạo bộ câu hỏi", key=f"btn_create_quiz_{notebook_id}_{doc_key}"):
            with st.spinner("Đang thiết lập..."):
                filters = {"notebook_id": notebook_id}
                if page_filter:
                    filters["page"] = page_filter

                payload = {"document": selected_doc, "count": count, "filters": filters}
                res = _api("POST", "/quiz", json=payload)
                if _has_learning_items(res, "items"):
                    _clear_state_prefix(option_prefix)
                    st.session_state[quiz_key] = res
                    st.session_state[answers_key] = {}
                    st.session_state[submitted_key] = False
                    st.rerun()
                elif res is not None:
                    st.warning("Chưa tạo được câu hỏi nào từ tài liệu này. Hãy thử chọn tài liệu cụ thể hoặc giảm phạm vi tài liệu.")
    
    with col_btn2:
        if quiz_key in st.session_state:
            if st.button("🗑️ Xóa bài tập này", type="primary", key=f"btn_del_quiz_{notebook_id}_{doc_key}"):
                _api("DELETE", f"/notebooks/{notebook_id}/learning/quiz", params={"document": doc_key})
                del st.session_state[quiz_key]
                st.session_state.pop(answers_key, None)
                st.session_state.pop(submitted_key, None)
                _clear_state_prefix(option_prefix)
                st.rerun()

    if quiz_key in st.session_state:
        quiz_data = st.session_state[quiz_key]
        if not _has_learning_items(quiz_data, "items"):
            st.warning("Bộ trắc nghiệm đã lưu trước đó không có câu hỏi. Hãy xóa và tạo lại bộ mới.")
            return
        if answers_key not in st.session_state:
            st.session_state[answers_key] = {}
        for idx, item in enumerate(quiz_data["items"]):
            option_key = f"{option_prefix}{idx}"
            current_selection = st.session_state[answers_key].get(idx)
            selected_option = st.radio(
                f"**Câu {idx+1}: {item['question']}**",
                item["options"],
                key=option_key,
                index=current_selection,
                disabled=st.session_state.get(submitted_key, False)
            )
            if selected_option is not None:
                st.session_state[answers_key][idx] = item["options"].index(selected_option)

            if st.session_state.get(submitted_key, False):
                user_ans = st.session_state[answers_key].get(idx)
                correct_ans = item["correct_index"]
                if user_ans == correct_ans:
                    st.success("✅ Chính xác!")
                else:
                    st.error(f"❌ Sai! Đáp án đúng: {item['options'][correct_ans]}")
                st.info(f"Giải thích: {item['explanation']}")

        if not st.session_state.get(submitted_key, False):
            if st.button("Nộp bài", key=f"btn_submit_quiz_{notebook_id}_{doc_key}"):
                st.session_state[submitted_key] = True
                st.rerun()


@st.fragment
def _tab_flashcards(notebook_id, selected_doc, page_filter):
    doc_key = selected_doc or "all"
    fc_key = _state_key("active_flashcards", notebook_id, doc_key)
    fc_index_key = _state_key("flashcard_index", notebook_id, doc_key)
    fc_flipped_key = _state_key("flashcard_flipped", notebook_id, doc_key)
    st.markdown("<h2 style='font-family:Space Grotesk; font-weight:700;'>🗂️ Thẻ ghi nhớ (Flashcards)</h2>", unsafe_allow_html=True)
    count = st.slider("Số lượng thẻ", 5, 20, 8, key=f"sld_fc_count_{notebook_id}_{doc_key}")

    # Auto-load from NotebookStore
    if fc_key not in st.session_state:
        nb_res = _api("GET", f"/notebooks/{notebook_id}")
        if nb_res and "learning_data" in nb_res:
            saved_data = nb_res["learning_data"].get("flashcards", {}).get(doc_key)
            if _has_learning_items(saved_data, "cards"):
                st.session_state[fc_key] = saved_data
                st.session_state[fc_index_key] = 0
                st.session_state[fc_flipped_key] = False

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("Tạo thẻ", key=f"btn_create_fc_{notebook_id}_{doc_key}"):
            with st.spinner("Đang tạo thẻ..."):
                filters = {"notebook_id": notebook_id}
                if page_filter:
                    filters["page"] = page_filter

                payload = {"document": selected_doc, "count": count, "filters": filters}
                res = _api("POST", "/flashcards", json=payload)
                if _has_learning_items(res, "cards"):
                    st.session_state[fc_key] = res
                    st.session_state[fc_index_key] = 0
                    st.session_state[fc_flipped_key] = False
                    st.rerun()
                elif res is not None:
                    st.warning("Chưa tạo được flashcard nào từ tài liệu này. Hãy thử chọn tài liệu cụ thể hoặc giảm phạm vi tài liệu.")
                    
    with col_btn2:
        if fc_key in st.session_state:
            if st.button("🗑️ Xóa bài tập này", type="primary", key=f"btn_del_fc_{notebook_id}_{doc_key}"):
                _api("DELETE", f"/notebooks/{notebook_id}/learning/flashcards", params={"document": doc_key})
                del st.session_state[fc_key]
                st.session_state.pop(fc_index_key, None)
                st.session_state.pop(fc_flipped_key, None)
                st.rerun()

    if fc_key in st.session_state:
        fc_data = st.session_state[fc_key]
        if not _has_learning_items(fc_data, "cards"):
            st.warning("Bộ flashcards đã lưu trước đó đang rỗng. Hãy xóa và tạo lại bộ mới.")
            return
        idx = st.session_state.get(fc_index_key, 0)
        idx = max(0, min(idx, len(fc_data["cards"]) - 1))
        st.session_state[fc_index_key] = idx
        card = fc_data["cards"][idx]

        # Callbacks to update state instantly in Streamlit fragment without full rerun lag
        def go_prev():
            st.session_state[fc_index_key] = idx - 1
            st.session_state[fc_flipped_key] = False

        def go_next():
            st.session_state[fc_index_key] = idx + 1
            st.session_state[fc_flipped_key] = False

        def flip_card(target_val):
            st.session_state[fc_flipped_key] = target_val

        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            st.button(
                "◀️ Trước",
                disabled=(idx == 0),
                use_container_width=True,
                key=f"btn_prev_fc_{notebook_id}_{doc_key}",
                on_click=go_prev
            )
        with col2:
            st.markdown(f"<div style='text-align:center; padding-top: 5px;'>Thẻ {idx+1} / {len(fc_data['cards'])}</div>", unsafe_allow_html=True)
        with col3:
            st.button(
                "Sau ▶️",
                disabled=(idx == len(fc_data["cards"]) - 1),
                use_container_width=True,
                key=f"btn_next_fc_{notebook_id}_{doc_key}",
                on_click=go_next
            )

        # Single markdown block renders container and content together to avoid open/close splitting
        is_flipped = st.session_state.get(fc_flipped_key, False)
        card_content = card['back'] if is_flipped else card['front']
        card_color_style = "color:#a5b4fc;" if is_flipped else ""
        card_side_label = "MẶT SAU (TRẢ LỜI)" if is_flipped else "MẶT TRƯỚC (CÂU HỎI)"
        
        st.markdown(f"""
        <div class='flashcard-container'>
            <div class='flashcard-topic'>{card_side_label}</div>
            <div class='flashcard-content' style='{card_color_style}'>{card_content}</div>
            {"<div class='flashcard-hint'>💡 Gợi ý: " + card['hint'] + "</div>" if not is_flipped and card.get('hint') else ""}
        </div>
        """, unsafe_allow_html=True)

        if not is_flipped:
            st.button(
                "🔄 Lật mặt sau",
                use_container_width=True,
                key=f"btn_flip_back_{notebook_id}_{doc_key}_{idx}",
                on_click=flip_card,
                args=(True,)
            )
        else:
            st.button(
                "🔄 Lật mặt trước",
                use_container_width=True,
                key=f"btn_flip_front_{notebook_id}_{doc_key}_{idx}",
                on_click=flip_card,
                args=(False,)
            )


def run():
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    page = st.session_state.page
    
    if page == "landing":
        render_landing()
    elif page == "dashboard":
        render_dashboard()
    elif page == "notebook":
        nb_id = st.session_state.notebook_id
        nb_name = st.session_state.notebook_name
        
        nb_res = _api("GET", f"/notebooks/{nb_id}")
        
        selected_doc, page_filter = _sidebar_notebook(nb_id, nb_name)
        
        # Chặn xử lý nội dung chính nếu có tài liệu đang được nạp (hoặc bị kẹt)
        is_processing = False
        if nb_res and "documents" in nb_res:
            for doc in nb_res["documents"]:
                if doc.get("chunks_indexed", 0) == 0:
                    is_processing = True
                    break
                    
        if is_processing:
            st.warning("⏳ Hệ thống đang nạp tài liệu. Nếu bị kẹt quá lâu do sập nguồn, bạn có thể ấn nút 🗑️ ở bên trái để xóa tài liệu bị kẹt.")
            import time
            time.sleep(3)
            st.rerun()
            return
        
        # Thêm cảnh báo nếu tạo quá nhiều tài liệu học tập
        if nb_res and "learning_data" in nb_res:
            total_materials = sum(len(docs) for docs in nb_res["learning_data"].values())
            if total_materials > 10:
                st.warning(f"⚠️ Cảnh báo: Bạn đang lưu trữ {total_materials} bài tập trong thẻ này. Hãy xem xét xóa bớt những tài liệu học xong rồi hoặc không học nữa để giải phóng không gian ổ cứng!")

        tabs = st.tabs(["💬 Hỏi đáp", "📝 Tóm tắt", "🧠 Trắc nghiệm", "🗂️ Flashcards"])
        with tabs[0]:
            _tab_chat(nb_id, selected_doc, page_filter)
        with tabs[1]:
            _tab_summary(nb_id, selected_doc, page_filter)
        with tabs[2]:
            _tab_quiz(nb_id, selected_doc, page_filter)
        with tabs[3]:
            _tab_flashcards(nb_id, selected_doc, page_filter)

if __name__ == "__main__":
    run()
