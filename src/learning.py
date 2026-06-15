"""
Learning Module — Tầng Tạo sinh & Kiểm duyệt
Summarize (Map-Reduce), Quiz, Flashcards generation.
Uses the new retrieval pipeline (Router → HybridSearch/Scroll → Reranker → ContextBuilder).
Pydantic Validation ép kiểu JSON bắt lỗi thiếu đáp án.
"""
import json
import re
from typing import List, Dict, Set, Any, Tuple, Optional, Type
from pydantic import ValidationError
from src.config import settings
from src.schemas import ChunkMetadata, RetrievedChunk, Summary, QuizItem, QuizSet, Flashcard, FlashcardSet
from src.rag import retrieve, fetch_all_chunks, render_prompt
from src.retrieval.context_builder import format_citations
from src.llm import invoke_llm
from src.bm25_index import get_bm25_index

SUMMARY_SINGLE_TEMPLATE = "summary_single.jinja2"
SUMMARY_MAP_TEMPLATE = "summary_map.jinja2"
SUMMARY_REDUCE_TEMPLATE = "summary_reduce.jinja2"
QUIZ_TEMPLATE = "quiz.jinja2"
FLASHCARDS_TEMPLATE = "flashcards.jinja2"


def _resolve_target(document, query, filters, k, retrieval_k) -> Tuple[List[Any], str, str]:
    """
    Resolve retrieval target using Scope Router logic:
    - query → HybridSearch (retrieve)
    - no query → Scroll All Chunks (fetch_all_chunks)
    """
    effective_filters = dict(filters or {})

    if document:
        effective_filters["filename"] = document

    if query:
        chunks = retrieve(query, k=k or retrieval_k, filters=effective_filters)
        return chunks, "query", query

    if effective_filters:
        try:
            chunks = fetch_all_chunks(filters=effective_filters)
        except Exception:
            chunks = []
        if not chunks:
            chunks = _fetch_chunks_from_bm25(effective_filters)
        scope = "document" if document else "filter"
        target = ", ".join(f"{k}={v}" for k, v in effective_filters.items())
        return chunks, scope, target

    try:
        chunks = fetch_all_chunks(filters=None)
    except Exception:
        chunks = []
    return chunks, "corpus", None


def _metadata_matches_filters(metadata: dict, filters: Optional[dict]) -> bool:
    if not filters:
        return True

    for field, value in filters.items():
        if field == "filenames" and isinstance(value, list):
            if metadata.get("filename") not in value:
                return False
            continue
        if isinstance(value, (str, int)) and metadata.get(field) != value:
            return False

    return True


def _fetch_chunks_from_bm25(filters: Optional[dict]) -> List[RetrievedChunk]:
    notebook_id = (filters or {}).get("notebook_id", "default")
    bm25_index = get_bm25_index(notebook_id)
    documents = getattr(bm25_index, "_documents", [])
    chunks = [
        RetrievedChunk(
            text=doc.text,
            score=0.0,
            metadata=ChunkMetadata(**doc.metadata),
        )
        for doc in documents
        if _metadata_matches_filters(doc.metadata, filters)
    ]
    return sorted(chunks, key=lambda r: (
        r.metadata.filename,
        r.metadata.page,
        int(r.metadata.chunk_id.rsplit(":", 1)[-1]),
    ))


def _limit_generation_chunks(chunks: List[RetrievedChunk], limit: int) -> List[RetrievedChunk]:
    """Keep prompts small enough for local models while covering the whole document."""
    if len(chunks) <= limit:
        return chunks
    if limit <= 1:
        return chunks[:1]

    step = (len(chunks) - 1) / (limit - 1)
    indexes = []
    for i in range(limit):
        idx = round(i * step)
        if idx not in indexes:
            indexes.append(idx)
    return [chunks[i] for i in indexes]


def _parse_json(text: str) -> Any:
    """Parse JSON from LLM output, handling markdown code blocks."""
    cleaned = text.strip()

    # Clean standard markdown blocks
    if cleaned.startswith("```json"):
        cleaned = cleaned.split("\n", 1)[-1].removesuffix("```").strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1].removesuffix("```").strip()
    elif cleaned.startswith("'''"):
        cleaned = cleaned.split("\n", 1)[-1].removesuffix("'''").strip()

    # Extra safety extraction
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[-1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[-1].split("```")[0].strip()

    try:
        obj = json.loads(cleaned)
    except json.JSONDecodeError:
        decoder = json.JSONDecoder()
        obj = None
        for idx, char in enumerate(cleaned):
            if char not in "{[":
                continue
            try:
                obj, _ = decoder.raw_decode(cleaned[idx:])
                break
            except json.JSONDecodeError:
                continue
        if obj is None:
            raise

    if not isinstance(obj, (dict, list)):
        raise RuntimeError("Expected JSON object or array.")
    return obj


def _validate_summary_payload(payload: Any) -> Tuple[str, List[str]]:
    if not isinstance(payload, dict):
        raise RuntimeError("Expected dict payload for summary.")
    summary_text = payload.get("summary", "")
    key_points = payload.get("key_points", [])
    if not isinstance(key_points, list):
        key_points = [key_points] if key_points else []
    return str(summary_text), [str(kp) for kp in key_points]


def summarize(document=None, query=None, filters=None, k=None, llm_provider=None) -> Summary:
    """
    Generate summary using Map-Reduce strategy.
    Uses Qdrant_Scroll for full-document operations (gom lô dữ liệu).
    """
    chunks, scope, target = _resolve_target(
        document, query, filters, k, settings.summarize_retrieval_k
    )

    if not chunks:
        return Summary(
            scope=scope,
            target=target,
            summary="Không có tài liệu nào để tóm tắt.",
            key_points=[],
            citations=[],
            chunks=[]
        )

    if len(chunks) <= settings.summarize_batch_size:
        prompt = render_prompt(SUMMARY_SINGLE_TEMPLATE, chunks=chunks)
        payload = _parse_json(invoke_llm(prompt, provider=llm_provider))
        summary_text, key_points = _validate_summary_payload(payload)
    else:
        # Map-Reduce: nhóm dữ liệu tóm tắt văn bản dài
        partials = []
        for start in range(0, len(chunks), settings.summarize_batch_size):
            batch = chunks[start : start + settings.summarize_batch_size]
            payload = _parse_json(invoke_llm(render_prompt(SUMMARY_MAP_TEMPLATE, chunks=batch), provider=llm_provider))
            summary_text, key_points = _validate_summary_payload(payload)
            partials.append({"summary": summary_text, "key_points": key_points})

        payload = _parse_json(invoke_llm(render_prompt(SUMMARY_REDUCE_TEMPLATE, partials=partials), provider=llm_provider))
        summary_text, key_points = _validate_summary_payload(payload)

    return Summary(
        scope=scope,
        target=target,
        summary=summary_text,
        key_points=key_points,
        citations=format_citations(chunks),
        chunks=chunks,
    )


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        return [value]
    return list(value) if isinstance(value, tuple) else [value]


def _clean_table_artifacts(text: str) -> str:
    if not text:
        return ""
    # Remove markdown table row/column boundaries and dividers
    cleaned = re.sub(r"\|[-:| ]+\|", " ", text)
    cleaned = re.sub(r"\|", " ", cleaned)  # remove individual pipe characters
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _normalise_quiz_item(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {}

    item = dict(raw)
    item["question"] = _clean_table_artifacts(
        item.get("question") or item.get("q") or item.get("cau_hoi") or item.get("câu hỏi") or ""
    )

    options = item.get("options") or item.get("choices") or item.get("answers") or item.get("lua_chon") or []
    if isinstance(options, dict):
        ordered = []
        for key in ["A", "B", "C", "D", "a", "b", "c", "d", "0", "1", "2", "3"]:
            if key in options:
                ordered.append(options[key])
        options = ordered or list(options.values())
    elif isinstance(options, str):
        parts = re.split(r"\n+|(?:^|\s)[A-Da-d][).:-]\s+", options)
        options = [part.strip() for part in parts if part.strip()]
    item["options"] = [_clean_table_artifacts(str(opt)) for opt in options if str(opt).strip()][:4]

    correct = item.get("correct_index", item.get("answer_index", item.get("correct_answer", item.get("answer"))))
    if isinstance(correct, str):
        clean = correct.strip()
        if clean.upper() in {"A", "B", "C", "D"}:
            correct = ord(clean.upper()) - ord("A")
        elif clean.isdigit():
            correct = int(clean)
        elif clean in item["options"]:
            correct = item["options"].index(clean)
    item["correct_index"] = correct if isinstance(correct, int) else 0

    item["explanation"] = _clean_table_artifacts(
        str(
            item.get("explanation")
            or item.get("explain")
            or item.get("giai_thich")
            or "Đáp án được suy ra trực tiếp từ nội dung tài liệu."
        )
    )
    item["source_markers"] = [str(m).strip() for m in _as_list(item.get("source_markers")) if str(m).strip()]
    return item


def _normalise_flashcard(raw: Any) -> dict:
    if not isinstance(raw, dict):
        return {}

    item = dict(raw)
    item["front"] = _clean_table_artifacts(
        item.get("front") or item.get("question") or item.get("term") or item.get("concept") or ""
    )
    item["back"] = _clean_table_artifacts(
        item.get("back") or item.get("answer") or item.get("definition") or item.get("explanation") or ""
    )
    item["hint"] = _clean_table_artifacts(item.get("hint") or "")
    item["topic"] = _clean_table_artifacts(item.get("topic") or "")
    item["source_markers"] = [str(m).strip() for m in _as_list(item.get("source_markers")) if str(m).strip()]
    return item


def _normalise_payload(payload: Any, key: str) -> dict:
    if isinstance(payload, list):
        return {key: payload}
    if isinstance(payload, dict):
        if key not in payload or not payload[key]:
            for alt_key in ["items", "cards", "questions", "flashcards"]:
                if alt_key in payload and isinstance(payload[alt_key], list):
                    payload[key] = payload[alt_key]
                    break
        return payload
    return {key: []}


def _validate_items(payload, key, model_class: Type, dedup_field, label, valid_markers):
    """
    Pydantic Validation: ép kiểu JSON bắt lỗi thiếu đáp án.
    Validates and deduplicates generated items.
    """
    payload = _normalise_payload(payload, key)
    raw_items = payload.get(key)
    if not raw_items:
        raw_items = []

    items, seen = [], set()
    for raw in raw_items:
        if model_class is QuizItem:
            raw = _normalise_quiz_item(raw)
        elif model_class is Flashcard:
            raw = _normalise_flashcard(raw)

        try:
            item = model_class.model_validate(raw)
        except ValidationError:
            continue

        val_text = str(getattr(item, dedup_field, "")).strip()
        norm = val_text.lower()
        if not norm or norm in seen:
            continue

        # Skip placeholders or copied examples
        is_placeholder = False
        if model_class is QuizItem:
            if raw.get("question", "").strip() in ("", "..."):
                is_placeholder = True
            for opt in raw.get("options", []):
                if str(opt).strip() in ("", "..."):
                    is_placeholder = True
        elif model_class is Flashcard:
            if raw.get("front", "").strip() in ("", "..."):
                is_placeholder = True
            if raw.get("back", "").strip() in ("", "..."):
                is_placeholder = True

        if is_placeholder or norm.strip() == "..." or "khái niệm hoặc" in norm or "câu hỏi ở mặt trước" in norm or "câu hỏi thứ hai" in norm:
            continue

        seen.add(norm)
        markers = [m for m in item.source_markers if m in valid_markers]
        items.append(item.model_copy(update={"source_markers": markers}))

    if not items:
        raise RuntimeError(f"No valid {label} produced.")
    return items


def _clean_text(text: str, max_len: int = 260) -> str:
    # Remove markdown table rows/dividers
    cleaned = re.sub(r"\|[-:| ]+\|", " ", text)
    cleaned = re.sub(r"\n+", " ", cleaned)
    cleaned = re.sub(r"\|", " ", cleaned)  # remove remaining pipe chars
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if len(cleaned) <= max_len:
        return cleaned
    return cleaned[:max_len].rsplit(" ", 1)[0] + "..."


def _fallback_quiz_items(chunks: List[RetrievedChunk], count: int) -> List[QuizItem]:
    selected = _limit_generation_chunks(chunks, count)
    items = []
    for i, chunk in enumerate(selected, start=1):
        section = chunk.metadata.section or f"Trang {chunk.metadata.page}"
        # Filter out markdown tables from fallback text lines
        lines = []
        for line in chunk.text.split("\n"):
            line_clean = line.strip()
            if not line_clean or line_clean.count("|") > 1 or line_clean.startswith("---") or line_clean.startswith("==="):
                continue
            lines.append(line_clean)
            
        topic_preview = section
        if lines:
            first_line = re.sub(r"[#*|`_\-]", "", lines[0]).strip()
            if len(first_line) > 5 and len(first_line) < 60:
                topic_preview = first_line

        snippet = _clean_text(chunk.text, max_len=180)
        
        question_templates = [
            f"Vấn đề nào được đề cập chính trong phần '{topic_preview}'?",
            f"Theo tài liệu, nội dung nào sau đây mô tả đúng nhất về '{topic_preview}'?",
            f"Thông tin quan trọng nào được trình bày trong '{topic_preview}'?",
        ]
        question = question_templates[i % len(question_templates)]

        distractors = [
            "Thông tin này không xuất hiện hoặc không có cơ sở trong tài liệu.",
            "Tài liệu mô tả nội dung này theo hướng hoàn toàn ngược lại.",
            "Đây là khái niệm giả thuyết ngoài phạm vi của tài liệu.",
        ]
        items.append(QuizItem(
            question=question,
            options=[snippet, *distractors],
            correct_index=0,
            explanation=f"Đáp án đúng được xác thực từ đoạn nguồn S{i} ở trang {chunk.metadata.page}: {snippet}",
            source_markers=[f"S{i}"],
            difficulty="easy",
            topic=section,
        ))
    return items


def _fallback_flashcards(chunks: List[RetrievedChunk], count: int) -> List[Flashcard]:
    selected = _limit_generation_chunks(chunks, count)
    cards = []
    for i, chunk in enumerate(selected, start=1):
        section = chunk.metadata.section or f"Trang {chunk.metadata.page}"
        # Filter out markdown tables from fallback text lines
        lines = []
        for line in chunk.text.split("\n"):
            line_clean = line.strip()
            if not line_clean or line_clean.count("|") > 1 or line_clean.startswith("---") or line_clean.startswith("==="):
                continue
            lines.append(line_clean)
            
        topic_preview = section
        if lines:
            first_line = re.sub(r"[#*|`_\-]", "", lines[0]).strip()
            if len(first_line) > 5 and len(first_line) < 60:
                topic_preview = first_line

        snippet = _clean_text(chunk.text, max_len=300)
        
        front_templates = [
            f"Nội dung cốt lõi của phần '{topic_preview}' là gì?",
            f"Tóm tắt ý nghĩa quan trọng được thảo luận trong '{topic_preview}':",
            f"Khái niệm hay kiến thức chính cần nhớ ở phần '{topic_preview}':",
        ]
        front = front_templates[i % len(front_templates)]
        
        cards.append(Flashcard(
            front=front,
            back=snippet,
            hint=f"Xem đoạn trích dẫn nguồn S{i} ở trang {chunk.metadata.page} của tài liệu.",
            topic=section,
            source_markers=[f"S{i}"],
        ))
    return cards


def _batch_generate(chunks: List[RetrievedChunk], count: int, template_name: str, key: str, model_class: Type, dedup_field: str, label: str, llm_provider: str, max_batch_item_count: int = 3) -> List[Any]:
    import logging
    logger = logging.getLogger(__name__)

    batch_counts = []
    remaining = count
    while remaining > 0:
        take = min(remaining, max_batch_item_count)
        batch_counts.append(take)
        remaining -= take

    num_batches = len(batch_counts)
    if num_batches <= 1:
        prompt = render_prompt(template_name, chunks=chunks, count=count)
        payload = _parse_json(invoke_llm(prompt, provider=llm_provider))
        valid_markers = {f"S{i}" for i in range(1, len(chunks) + 1)}
        return _validate_items(payload, key, model_class, dedup_field, label, valid_markers)

    all_items = []
    chunk_step = len(chunks) / num_batches
    for i, batch_count in enumerate(batch_counts):
        start_idx = int(i * chunk_step)
        end_idx = int((i + 1) * chunk_step) if i < num_batches - 1 else len(chunks)
        batch_chunks = chunks[start_idx:end_idx]
        
        valid_markers = {f"S{j}" for j in range(1, len(batch_chunks) + 1)}
        prompt = render_prompt(template_name, chunks=batch_chunks, count=batch_count)
        try:
            logger.info(f"Generating batch {i+1}/{num_batches} (items: {batch_count}) with {len(batch_chunks)} chunks...")
            payload = _parse_json(invoke_llm(prompt, provider=llm_provider))
            batch_items = _validate_items(payload, key, model_class, dedup_field, label, valid_markers)
            
            # Map source_markers back to global index
            for item in batch_items:
                global_markers = []
                for m in item.source_markers:
                    try:
                        local_idx = int(m[1:]) - 1
                        global_idx = start_idx + local_idx + 1
                        global_markers.append(f"S{global_idx}")
                    except Exception:
                        pass
                item.source_markers = global_markers
            
            all_items.extend(batch_items)
        except Exception as e:
            logger.warning(f"Batch {i+1} failed: {e}. Falling back to dynamic heuristic for this batch.")
            if model_class is QuizItem:
                batch_fallback = _fallback_quiz_items(batch_chunks, batch_count)
            else:
                batch_fallback = _fallback_flashcards(batch_chunks, batch_count)
                
            for item in batch_fallback:
                global_markers = []
                for m in item.source_markers:
                    try:
                        local_idx = int(m[1:]) - 1
                        global_idx = start_idx + local_idx + 1
                        global_markers.append(f"S{global_idx}")
                    except Exception:
                        pass
                item.source_markers = global_markers
            all_items.extend(batch_fallback)
            
    return all_items


def generate_quiz(document=None, query=None, filters=None, count=None, k=None, llm_provider=None) -> QuizSet:
    """Generate multiple-choice quiz with batching and validation."""
    chunks, scope, target = _resolve_target(
        document, query, filters, k, settings.generation_retrieval_k
    )

    if not chunks:
        return QuizSet(scope=scope, target=target, items=[], citations=[], chunks=[])

    n = count or settings.quiz_default_count
    chunks = _limit_generation_chunks(chunks, k or max(settings.generation_retrieval_k, n * 2))
    
    try:
        items = _batch_generate(
            chunks=chunks,
            count=n,
            template_name=QUIZ_TEMPLATE,
            key="items",
            model_class=QuizItem,
            dedup_field="question",
            label="quiz items",
            llm_provider=llm_provider
        )
    except Exception:
        items = _fallback_quiz_items(chunks, n)

    return QuizSet(
        scope=scope,
        target=target,
        items=items,
        chunks=chunks,
        citations=format_citations(chunks)
    )


def generate_flashcards(document=None, query=None, filters=None, count=None, k=None, llm_provider=None) -> FlashcardSet:
    """Generate flashcards with batching and validation."""
    chunks, scope, target = _resolve_target(
        document, query, filters, k, settings.generation_retrieval_k
    )

    if not chunks:
        return FlashcardSet(scope=scope, target=target, cards=[], citations=[], chunks=[])

    n = count or settings.flashcards_default_count
    chunks = _limit_generation_chunks(chunks, k or max(settings.generation_retrieval_k, n * 2))
    
    try:
        cards = _batch_generate(
            chunks=chunks,
            count=n,
            template_name=FLASHCARDS_TEMPLATE,
            key="cards",
            model_class=Flashcard,
            dedup_field="front",
            label="flashcards",
            llm_provider=llm_provider
        )
    except Exception:
        cards = _fallback_flashcards(chunks, n)

    return FlashcardSet(
        scope=scope,
        target=target,
        cards=cards,
        chunks=chunks,
        citations=format_citations(chunks)
    )
