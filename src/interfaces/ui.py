"""
Streamlit Web UI â€” Táº§ng Giao diá»‡n Multi-Workspace (Notebooks)
MÃ´ phá»ng tráº£i nghiá»‡m Google NotebookLM.
"""
import streamlit as st
import httpx
import json
import uuid
import sys
import os

# Äáº£m báº£o Python nháº­n diá»‡n Ä‘Æ°á»£c thÆ° má»¥c gá»‘c cá»§a dá»± Ã¡n Ä‘á»ƒ import 'src'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.utils.config import settings
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
                st.error("ðŸ”‘ **Lá»—i cáº¥u hÃ¬nh API Key:** Vui lÃ²ng kiá»ƒm tra file `.env`.")
            else:
                st.error(f"âŒ **Lá»—i tá»« Backend:** {detail}")
            return None
        return res.json()
    except Exception as e:
        st.error(f"Lá»—i káº¿t ná»‘i Ä‘áº¿n API backend: {e}")
        return None

def _api_stream(path: str, payload: dict):
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
                yield f"\n\nâš ï¸ Lá»—i há»‡ thá»‘ng ({response.status_code}): {detail}"
                return

            for line in response.iter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if "text" in data:
                        yield data["text"]
                    if data.get("done"):
                        break
    except Exception as e:
        yield f"\n\nâš ï¸ Lá»—i káº¿t ná»‘i Ä‘áº¿n Backend: {e}"

# -----------------------------------------------------------------------------
# Tráº¡ng thÃ¡i há»‡ thá»‘ng (State Machine)
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
    st.markdown("<div style='text-align:center; padding-top: 100px;'>", unsafe_allow_html=True)
    st.markdown("<h1 style='font-size: 4rem; font-family: Space Grotesk; color: #818cf8;'>NotebookLM</h1>", unsafe_allow_html=True)
    st.markdown("<p style='font-size: 1.2rem; color: #94a3b8;'>Há»‡ thá»‘ng RAG há»— trá»£ há»c táº­p vÃ  nghiÃªn cá»©u thÃ´ng minh cá»§a riÃªng báº¡n.</p>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("DÃ¹ng thá»­ NotebookLM", use_container_width=False, type="primary"):
        navigate_to("dashboard")
    st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Trang 2: Dashboard (Danh sÃ¡ch Tháº» / Notebooks)
# -----------------------------------------------------------------------------
def render_dashboard():
    st.markdown("<h1 style='font-family: Space Grotesk; color: #818cf8;'>ðŸ““ Tháº» cá»§a tÃ´i (Notebooks)</h1>", unsafe_allow_html=True)
    st.markdown("<p style='color: #94a3b8;'>Táº¡o tháº» má»›i hoáº·c chá»n má»™t tháº» Ä‘Ã£ cÃ³ Ä‘á»ƒ tiáº¿p tá»¥c lÃ m viá»‡c.</p>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([3, 1])
    with col1:
        new_name = st.text_input("TÃªn Tháº» Má»›i", placeholder="Nháº­p tÃªn tháº»... (VD: Lá»‹ch sá»­, AI Research...)")
    
    st.markdown("**Chá»n AI Backend cho tháº» nÃ y:**")
    provider_options = {
        "ðŸ–¥ï¸ Universal Local AI (RiÃªng tÆ°, 100% tá»± Ä‘á»™ng tÆ°Æ¡ng thÃ­ch má»i pháº§n cá»©ng)": "hf_local",
        "ðŸŒ Gemini API (Nhanh, cáº§n API Key â€” âš ï¸ khÃ´ng dÃ¹ng vá»›i data riÃªng tÆ°)": "gemini"
    }
    selected_provider_label = st.selectbox(
        "LLM Backend",
        list(provider_options.keys()),
        label_visibility="collapsed",
    )
    selected_provider = provider_options[selected_provider_label]
    if selected_provider == "gemini":
        st.warning("âš ï¸ **LÆ°u Ã½:** Gemini API sáº½ gá»­i ná»™i dung tÃ i liá»‡u cá»§a báº¡n lÃªn mÃ¡y chá»§ Google. KhÃ´ng nÃªn dÃ¹ng vá»›i dá»¯ liá»‡u riÃªng tÆ°/nháº¡y cáº£m.")

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("âž• Táº¡o Tháº» Má»›i", use_container_width=True):
            if new_name.strip():
                with st.spinner("Äang táº¡o tháº»..."):
                    res = _api("POST", "/notebooks", json={"name": new_name.strip(), "llm_provider": selected_provider})
                    if res:
                        navigate_to("notebook", res["id"], res["name"])
            else:
                st.warning("Vui lÃ²ng nháº­p tÃªn tháº».")

    st.markdown("---")
    
    notebooks = _api("GET", "/notebooks")
    if not notebooks:
        st.info("Báº¡n chÆ°a cÃ³ Tháº» nÃ o. HÃ£y táº¡o Tháº» má»›i á»Ÿ trÃªn.")
        return

    # Hiá»ƒn thá»‹ dáº¡ng Grid
    cols = st.columns(3)
    for idx, nb in enumerate(notebooks):
        with cols[idx % 3]:
            st.markdown(f"<div class='glass-card' style='height: 150px; cursor: pointer;'>", unsafe_allow_html=True)
            st.markdown(f"<h3 style='margin-bottom:0;'>{nb['name']}</h3>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-size: 0.8rem; color: #94a3b8;'>{len(nb['documents'])} tÃ i liá»‡u</p>", unsafe_allow_html=True)
            
            c1, c2 = st.columns(2)
            with c1:
                if st.button("Má»Ÿ ðŸ“‚", key=f"open_{nb['id']}", use_container_width=True):
                    with st.spinner("Äang má»Ÿ tháº»..."):
                        navigate_to("notebook", nb["id"], nb["name"])
            with c2:
                if st.button("XÃ³a ðŸ—‘ï¸", key=f"del_{nb['id']}", use_container_width=True):
                    _api("DELETE", f"/notebooks/{nb['id']}")
                    st.rerun()
            # Show provider badge
            provider_badge = {
                "gemini": "ðŸŒ Gemini API",
                "hf_local": "ðŸ–¥ï¸ Local HF",
                "vllm": "âš¡ vLLM",
            }.get(nb.get("llm_provider", "gemini"), "ðŸŒ Gemini API")
            st.caption(f"AI: {provider_badge}")
            st.markdown("</div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Trang 3: Notebook View (Trong má»™t tháº» cá»¥ thá»ƒ)
# -----------------------------------------------------------------------------
def _sidebar_notebook(notebook_id: str, notebook_name: str):
    if st.sidebar.button("â¬…ï¸ Trá»Ÿ vá» Dashboard"):
        navigate_to("dashboard")
        
    st.sidebar.markdown(f"<h2 style='font-family:Space Grotesk; font-weight:700; color:#818cf8;'>ðŸ““ {notebook_name}</h2>", unsafe_allow_html=True)
    st.sidebar.markdown("---")

    # Upload
    uploaded_file = st.sidebar.file_uploader(
        "KÃ©o tháº£ tÃ i liá»‡u vÃ o Ä‘Ã¢y (Tá»± Ä‘á»™ng náº¡p)",
        type=["pdf", "docx", "pptx", "xlsx", "csv", "html", "md", "txt", "jpg", "jpeg", "png"],
    )

    # Fetch notebook info to check LLM provider
    nb_list = _api("GET", "/notebooks")
    nb_data = next((n for n in (nb_list or []) if n["id"] == notebook_id), None)
    is_gemini = nb_data and nb_data.get("llm_provider") == "gemini"

    # Privacy selection
    if is_gemini:
        privacy_choice = st.sidebar.radio(
            "NhÃ£n báº£o máº­t tÃ i liá»‡u:",
            ["ðŸŒ CÃ´ng khai (Public)", "ðŸ”’ RiÃªng tÆ° (Private)"],
            index=0,
            help="Private: cáº£nh bÃ¡o náº¿u notebook dÃ¹ng Gemini API (gá»­i data lÃªn cloud)",
        )
        privacy = "private" if "Private" in privacy_choice else "public"
    else:
        st.sidebar.success("ðŸ”’ **100% Local AI**\nDá»¯ liá»‡u khÃ´ng bao giá» rá»i khá»i mÃ¡y tÃ­nh.")
        privacy = "private"  # Always private for local models

    if uploaded_file is not None:
        if st.session_state.get("last_uploaded_file_id") != uploaded_file.file_id:
            st.session_state["last_uploaded_file_id"] = uploaded_file.file_id

            if privacy == "private" and is_gemini:
                st.sidebar.warning(
                    "âš ï¸ **Cáº£nh bÃ¡o Báº£o máº­t:** Tháº» nÃ y Ä‘ang dÃ¹ng **Gemini API** (cloud).\n\n"
                    "TÃ i liá»‡u **RiÃªng tÆ°** cá»§a báº¡n sáº½ Ä‘Æ°á»£c gá»­i Ä‘áº¿n mÃ¡y chá»§ Google Ä‘á»ƒ xá»­ lÃ½.\n\n"
                    "Vui lÃ²ng chá»n má»™t trong cÃ¡c tuá»³ chá»n bÃªn dÆ°á»›i:"
                )
                confirmed = st.sidebar.checkbox("âœ… TÃ´i hiá»ƒu rá»§i ro vÃ  váº«n muá»‘n tiáº¿p tá»¥c vá»›i Gemini API", key="privacy_confirm")

                if not confirmed:
                    st.sidebar.markdown("**Hoáº·c chuyá»ƒn sang Local AI Ä‘á»ƒ báº£o vá»‡ dá»¯ liá»‡u:**")
                    col_a, col_b = st.sidebar.columns(2)
                    with col_a:
                        if st.button("ðŸ–¥ï¸ DÃ¹ng Local HF", key="switch_hf", use_container_width=True):
                            _api("POST", f"/notebooks/{notebook_id}/provider", json={"llm_provider": "hf_local"})
                            st.session_state["last_uploaded_file_id"] = None  # reset Ä‘á»ƒ upload láº¡i
                            st.sidebar.success("âœ… ÄÃ£ chuyá»ƒn sang Local HF! HÃ£y táº£i file láº¡i.")
                            st.rerun()
                    with col_b:
                        if st.button("âš¡ DÃ¹ng vLLM", key="switch_vllm", use_container_width=True):
                            _api("POST", f"/notebooks/{notebook_id}/provider", json={"llm_provider": "vllm"})
                            st.session_state["last_uploaded_file_id"] = None
                            st.sidebar.success("âœ… ÄÃ£ chuyá»ƒn sang vLLM! HÃ£y táº£i file láº¡i.")
                            st.rerun()
                    st.sidebar.stop()

            with st.spinner("Äang xá»­ lÃ½ vÃ  nhÃºng Vector, vui lÃ²ng Ä‘á»£i..."):
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
                            st.sidebar.success(f"âœ… ÄÃ£ náº¡p xong: {status.get('filename')}")
                        elif status and status.get("status") == "error":
                            st.sidebar.error(f"âŒ Lá»—i: {status.get('error_message')}")
                        
                        st.rerun()



    st.sidebar.markdown("---")
    
    # Document List
    st.sidebar.markdown("### Nguá»“n (TÃ i liá»‡u Ä‘Ã£ náº¡p)")
    docs = _api("GET", f"/notebooks/{notebook_id}/documents")
    
    if not docs:
        st.sidebar.warning("Tháº» nÃ y chÆ°a cÃ³ tÃ i liá»‡u. Vui lÃ²ng táº£i lÃªn.")
        return None, None

    for d in docs:
        col1, col2 = st.sidebar.columns([4, 1])
        with col1:
            st.markdown(f"ðŸ“„ **{d['filename']}**", unsafe_allow_html=True)
        with col2:
            if st.button("ðŸ—‘ï¸", key=f"del_doc_{d['filename']}", help="XÃ³a tÃ i liá»‡u"):
                _api("DELETE", f"/notebooks/{notebook_id}/documents/{d['filename']}")
                st.rerun()
                
    st.sidebar.markdown("---")
    st.sidebar.markdown("### ðŸ” Bá»™ lá»c tÃ¬m kiáº¿m")
    doc_options = ["ToÃ n bá»™ tÃ i liá»‡u (Corpus)"] + [d["filename"] for d in docs]
    selected_doc = st.sidebar.selectbox("Chá»‰ Ä‘á»‹nh tÃ i liá»‡u", doc_options)
    doc_target = None if selected_doc == "ToÃ n bá»™ tÃ i liá»‡u (Corpus)" else selected_doc
    
    page_filter = None
    if doc_target:
        # We don't have page count in the simplified Notebook metadata yet, so fallback to simple text input or no filter
        st.sidebar.caption(f"Lá»c theo tÃ i liá»‡u: {doc_target}")

    return doc_target, page_filter


@st.fragment
def _tab_chat(notebook_id, selected_doc, page_filter):
    st.markdown("<h2 style='font-family:Space Grotesk; font-weight:700;'>ðŸ’¬ Há»i Ä‘Ã¡p vá»›i tÃ i liá»‡u</h2>", unsafe_allow_html=True)
    
    session_key = f"messages_{notebook_id}"
    if session_key not in st.session_state:
        nb_list = _api("GET", "/notebooks")
        nb_data = next((n for n in (nb_list or []) if n["id"] == notebook_id), None)
        st.session_state[session_key] = nb_data.get("messages", []) if nb_data else []

    use_streaming = st.checkbox("ðŸš€ Streaming mode (SSE)", value=True)

    if st.button("XÃ³a lá»‹ch sá»­ chat", type="secondary"):
        st.session_state[session_key] = []
        _api("DELETE", f"/notebooks/{notebook_id}/messages")
        st.rerun()

    for msg in st.session_state[session_key]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("citations"):
                with st.expander("ðŸ“š Nguá»“n trÃ­ch dáº«n (Citations)"):
                    for c in msg["citations"]:
                        st.markdown(f"<span class='source-tag'>{c['source_marker']}</span> <b>{c['filename']}</b> (Trang {c['page']})", unsafe_allow_html=True)

    query = st.chat_input("Nháº­p cÃ¢u há»i cá»§a báº¡n vá» tÃ i liá»‡u á»Ÿ Ä‘Ã¢y...")
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
                for chunk in _api_stream("/ask/stream", payload):
                    collected.append(chunk)
                    response_placeholder.markdown("".join(collected))

                full_answer = "".join(collected)
                msg_asst = {
                    "role": "assistant",
                    "content": full_answer,
                    "citations": [],
                }
                st.session_state[session_key].append(msg_asst)
                _api("POST", f"/notebooks/{notebook_id}/messages", json=msg_asst)
            else:
                with st.spinner("Äang suy nghÄ© vÃ  trÃ­ch xuáº¥t nguá»“n..."):
                    payload = {
                        "question": query,
                        "k": settings.top_k,
                        "filters": filters,
                        "session_id": _get_session_id(),
                    }
                    res = _api("POST", "/ask", json=payload)
                    if res:
                        st.markdown(res["answer"])
                        if res["citations"]:
                            with st.expander("ðŸ“š Nguá»“n trÃ­ch dáº«n (Citations)"):
                                for c in res["citations"]:
                                    st.markdown(f"<span class='source-tag'>{c['source_marker']}</span> <b>{c['filename']}</b> (Trang {c['page']})", unsafe_allow_html=True)

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
    st.markdown("<h2 style='font-family:Space Grotesk; font-weight:700;'>ðŸ“ HÆ°á»›ng dáº«n há»c táº­p (Study Guide)</h2>", unsafe_allow_html=True)
    summary_focus = st.text_input("Trá»ng tÃ¢m tÃ³m táº¯t (Äá»ƒ trá»‘ng Ä‘á»ƒ tÃ³m táº¯t toÃ n bá»™ tÃ i liá»‡u)", placeholder="VÃ­ dá»¥: cÃ¡c khÃ¡i niá»‡m cá»‘t lÃµi...")
    
    # Auto-load from NotebookStore
    if "active_summary" not in st.session_state:
        nb_res = _api("GET", f"/notebooks/{notebook_id}")
        if nb_res and "learning_data" in nb_res:
            saved_data = nb_res["learning_data"].get("summary", {}).get(doc_key)
            if saved_data:
                st.session_state["active_summary"] = saved_data

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("Táº¡o HÆ°á»›ng dáº«n"):
            with st.spinner("Äang phÃ¢n tÃ­ch..."):
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
                    st.session_state["active_summary"] = res
    with col_btn2:
        if "active_summary" in st.session_state:
            if st.button("ðŸ—‘ï¸ XÃ³a bÃ i táº­p nÃ y", type="primary"):
                _api("DELETE", f"/notebooks/{notebook_id}/learning/summary?document={doc_key}")
                del st.session_state["active_summary"]
                st.rerun()

    if "active_summary" in st.session_state:
        sum_data = st.session_state["active_summary"]
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("<h3 style='color:#818cf8;'>âœ¨ Báº£n tÃ³m táº¯t chÃ­nh</h3>", unsafe_allow_html=True)
        st.markdown(sum_data["summary"])
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.markdown("<h3 style='color:#818cf8;'>ðŸ“Œ CÃ¡c Ã½ chÃ­nh ná»•i báº­t</h3>", unsafe_allow_html=True)
        for kp in sum_data["key_points"]:
            st.markdown(f"- {kp}")
        st.markdown("</div>", unsafe_allow_html=True)


@st.fragment
def _tab_quiz(notebook_id, selected_doc, page_filter):
    doc_key = selected_doc or "all"
    st.markdown("<h2 style='font-family:Space Grotesk; font-weight:700;'>ðŸ“ Tráº¯c nghiá»‡m</h2>", unsafe_allow_html=True)
    count = st.slider("Sá»‘ lÆ°á»£ng cÃ¢u", 3, 15, 5)

    # Auto-load from NotebookStore
    if "active_quiz" not in st.session_state:
        nb_res = _api("GET", f"/notebooks/{notebook_id}")
        if nb_res and "learning_data" in nb_res:
            saved_data = nb_res["learning_data"].get("quiz", {}).get(doc_key)
            if saved_data:
                st.session_state["active_quiz"] = saved_data
                st.session_state["quiz_answers"] = {}
                st.session_state["quiz_submitted"] = False

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("Táº¡o bá»™ cÃ¢u há»i"):
            with st.spinner("Äang thiáº¿t láº­p..."):
                filters = {"notebook_id": notebook_id}
                if page_filter:
                    filters["page"] = page_filter

                payload = {"document": selected_doc, "count": count, "filters": filters}
                res = _api("POST", "/quiz", json=payload)
                if res and res.get("items"):
                    st.session_state["active_quiz"] = res
                    st.session_state["quiz_answers"] = {}
                    st.session_state["quiz_submitted"] = False
    
    with col_btn2:
        if "active_quiz" in st.session_state:
            if st.button("ðŸ—‘ï¸ XÃ³a bÃ i táº­p nÃ y", type="primary", key="btn_del_quiz"):
                _api("DELETE", f"/notebooks/{notebook_id}/learning/quiz?document={doc_key}")
                del st.session_state["active_quiz"]
                if "quiz_answers" in st.session_state: del st.session_state["quiz_answers"]
                if "quiz_submitted" in st.session_state: del st.session_state["quiz_submitted"]
                st.rerun()

    if "active_quiz" in st.session_state:
        quiz_data = st.session_state["active_quiz"]
        for idx, item in enumerate(quiz_data["items"]):
            st.markdown(f"<div style='font-weight:600; margin-top:20px;'>CÃ¢u {idx+1}: {item['question']}</div>", unsafe_allow_html=True)
            key = f"q_{idx}"
            selected_option = st.radio("Chá»n Ä‘Ã¡p Ã¡n:", item["options"], key=key, index=None, disabled=st.session_state["quiz_submitted"])
            if selected_option:
                st.session_state["quiz_answers"][idx] = item["options"].index(selected_option)

            if st.session_state["quiz_submitted"]:
                user_ans = st.session_state["quiz_answers"].get(idx)
                correct_ans = item["correct_index"]
                if user_ans == correct_ans:
                    st.success("âœ… ChÃ­nh xÃ¡c!")
                else:
                    st.error(f"âŒ Sai! ÄÃ¡p Ã¡n Ä‘Ãºng: {item['options'][correct_ans]}")
                st.info(f"Giáº£i thÃ­ch: {item['explanation']}")

        if not st.session_state["quiz_submitted"]:
            if st.button("Ná»™p bÃ i"):
                st.session_state["quiz_submitted"] = True
                st.rerun()


@st.fragment
def _tab_flashcards(notebook_id, selected_doc, page_filter):
    doc_key = selected_doc or "all"
    st.markdown("<h2 style='font-family:Space Grotesk; font-weight:700;'>ðŸ—‚ï¸ Tháº» ghi nhá»› (Flashcards)</h2>", unsafe_allow_html=True)
    count = st.slider("Sá»‘ lÆ°á»£ng tháº»", 5, 20, 8)

    # Auto-load from NotebookStore
    if "active_flashcards" not in st.session_state:
        nb_res = _api("GET", f"/notebooks/{notebook_id}")
        if nb_res and "learning_data" in nb_res:
            saved_data = nb_res["learning_data"].get("flashcards", {}).get(doc_key)
            if saved_data:
                st.session_state["active_flashcards"] = saved_data
                st.session_state["flashcard_index"] = 0
                st.session_state["flashcard_flipped"] = False

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("Táº¡o tháº»"):
            with st.spinner("Äang táº¡o tháº»..."):
                filters = {"notebook_id": notebook_id}
                if page_filter:
                    filters["page"] = page_filter

                payload = {"document": selected_doc, "count": count, "filters": filters}
                res = _api("POST", "/flashcards", json=payload)
                if res and res.get("cards"):
                    st.session_state["active_flashcards"] = res
                    st.session_state["flashcard_index"] = 0
                    st.session_state["flashcard_flipped"] = False
                    
    with col_btn2:
        if "active_flashcards" in st.session_state:
            if st.button("ðŸ—‘ï¸ XÃ³a bÃ i táº­p nÃ y", type="primary", key="btn_del_fc"):
                _api("DELETE", f"/notebooks/{notebook_id}/learning/flashcards?document={doc_key}")
                del st.session_state["active_flashcards"]
                if "flashcard_index" in st.session_state: del st.session_state["flashcard_index"]
                if "flashcard_flipped" in st.session_state: del st.session_state["flashcard_flipped"]
                st.rerun()

    if "active_flashcards" in st.session_state:
        fc_data = st.session_state["active_flashcards"]
        idx = st.session_state["flashcard_index"]
        card = fc_data["cards"][idx]

        col1, col2, col3 = st.columns([1, 2, 1])
        with col1:
            if st.button("â—€ï¸ TrÆ°á»›c", disabled=(idx == 0), use_container_width=True):
                st.session_state["flashcard_index"] -= 1
                st.session_state["flashcard_flipped"] = False
                st.rerun()
        with col2:
            st.markdown(f"<div style='text-align:center;'>Tháº» {idx+1} / {len(fc_data['cards'])}</div>", unsafe_allow_html=True)
        with col3:
            if st.button("Sau â–¶ï¸", disabled=(idx == len(fc_data["cards"]) - 1), use_container_width=True):
                st.session_state["flashcard_index"] += 1
                st.session_state["flashcard_flipped"] = False
                st.rerun()

        st.markdown("<div class='flashcard-container'>", unsafe_allow_html=True)
        if not st.session_state["flashcard_flipped"]:
            st.markdown(f"<div class='flashcard-content'>{card['front']}</div>", unsafe_allow_html=True)
            if st.button("ðŸ”„ Láº­t máº·t sau", use_container_width=True):
                st.session_state["flashcard_flipped"] = True
                st.rerun()
        else:
            st.markdown(f"<div class='flashcard-content' style='color:#a5b4fc;'>{card['back']}</div>", unsafe_allow_html=True)
            if st.button("ðŸ”„ Láº­t máº·t trÆ°á»›c", use_container_width=True):
                st.session_state["flashcard_flipped"] = False
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)


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
        
        # Cháº·n xá»­ lÃ½ ná»™i dung chÃ­nh náº¿u cÃ³ tÃ i liá»‡u Ä‘ang Ä‘Æ°á»£c náº¡p (hoáº·c bá»‹ káº¹t)
        is_processing = False
        if nb_res and "documents" in nb_res:
            for doc in nb_res["documents"]:
                if doc.get("chunks_indexed", 0) == 0:
                    is_processing = True
                    break
                    
        if is_processing:
            st.warning("â³ Há»‡ thá»‘ng Ä‘ang náº¡p tÃ i liá»‡u. Náº¿u bá»‹ káº¹t quÃ¡ lÃ¢u do sáº­p nguá»“n, báº¡n cÃ³ thá»ƒ áº¥n nÃºt ðŸ—‘ï¸ á»Ÿ bÃªn trÃ¡i Ä‘á»ƒ xÃ³a tÃ i liá»‡u bá»‹ káº¹t.")
            import time
            time.sleep(3)
            st.rerun()
            return
        
        # ThÃªm cáº£nh bÃ¡o náº¿u táº¡o quÃ¡ nhiá»u tÃ i liá»‡u há»c táº­p
        if nb_res and "learning_data" in nb_res:
            total_materials = sum(len(docs) for docs in nb_res["learning_data"].values())
            if total_materials > 10:
                st.warning(f"âš ï¸ Cáº£nh bÃ¡o: Báº¡n Ä‘ang lÆ°u trá»¯ {total_materials} bÃ i táº­p trong tháº» nÃ y. HÃ£y xem xÃ©t xÃ³a bá»›t nhá»¯ng tÃ i liá»‡u há»c xong rá»“i hoáº·c khÃ´ng há»c ná»¯a Ä‘á»ƒ giáº£i phÃ³ng khÃ´ng gian á»• cá»©ng!")

        tabs = st.tabs(["ðŸ’¬ Há»i Ä‘Ã¡p", "ðŸ“ TÃ³m táº¯t", "ðŸ§  Tráº¯c nghiá»‡m", "ðŸ—‚ï¸ Flashcards"])
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
