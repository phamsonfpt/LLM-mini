"""
Đánh giá kết quả RAG theo 4 metrics chuẩn RAGAS:
  - Faithfulness       : Câu trả lời AI có bịa đặt (hallucinate) không?
  - Answer Relevance   : Câu trả lời AI có liên quan đến câu hỏi không?
  - Context Recall     : Ngữ cảnh retrieved có đủ để suy ra đáp án chuẩn không?
  - Context Precision  : Ngữ cảnh retrieved có bị nhiễu (noise) không?

Cách dùng:
  python -m src.evaluation.ragas_evaluate

Yêu cầu:
  - File tests/ragbench_hotpotqa_full.csv đã có sẵn.
  - Backend server đang chạy (http://127.0.0.1:8000/v1/chat/completions).
"""

import sys
import json
import logging
import re
import time
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional

# ── UTF-8 cho Windows console ──────────────────────────────────────────────────
if sys.stdout.encoding != "utf-8":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ── Hằng số ────────────────────────────────────────────────────────────────────
INPUT_CSV   = Path("tests/ragbench_hotpotqa_full.csv")
OUTPUT_CSV  = Path("tests/ragbench_hotpotqa_10_ragas_gemini.csv")
GEMINI_KEY   = os.environ.get("GEMINI_API_KEY", "")   # set biến môi trường: $env:GEMINI_API_KEY="YOUR_KEY"
GEMINI_MODEL = "gemini-2.0-flash"
GEMINI_URL   = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_KEY}"
MAX_SAMPLES = 10     # 10 câu đầu
BATCH_PAUSE = 0.5    # giây nghỉ giữa các lần gọi để tránh rate-limit

# ── Gọi Gemini API với Retry + Backoff ────────────────────────────────────────
def call_llm(prompt: str, max_tokens: int = 512, retries: int = 5) -> str:
    """Gọi Gemini API với tự động retry khi bị 429 Rate Limit."""
    import urllib.request, urllib.error
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.0,
        }
    }).encode("utf-8")

    req = urllib.request.Request(
        GEMINI_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    wait = 5  # giây chờ ban đầu
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning(f"Rate limit 429 – chờ {wait}s rồi thử lại ({attempt+1}/{retries})...")
                time.sleep(wait)
                wait = min(wait * 2, 60)  # tăng gấp đôi, tối đa 60s
            else:
                logger.warning(f"Gemini HTTP Error {e.code}: {e.reason}")
                return ""
        except Exception as e:
            logger.warning(f"Gemini API call failed: {e}")
            return ""
    logger.warning("Đã hết số lần retry, trả về rỗng.")
    return ""


def parse_score(text: str, low: float = 0.0, high: float = 1.0) -> Optional[float]:
    """Trích xuất con số float đầu tiên trong chuỗi trả về của LLM."""
    matches = re.findall(r"\b([01](?:\.\d+)?|\d+(?:\.\d+)?)\b", text)
    for m in matches:
        v = float(m)
        if low <= v <= high:
            return round(v, 4)
    return None


# ── 4 Metrics ──────────────────────────────────────────────────────────────────

def score_faithfulness(question: str, context: str, answer_ai: str) -> Optional[float]:
    """
    Faithfulness: AI có nói điều gì KHÔNG có trong context không?
    Điểm 1.0 = hoàn toàn trung thực với context.
    Điểm 0.0 = bịa đặt hoàn toàn.
    """
    prompt = f"""You are an expert evaluator. Your task is to assess if the given answer is faithful to the provided context.

CONTEXT:
{context[:2000]}

QUESTION:
{question}

ANSWER:
{answer_ai[:800]}

Instructions:
- Score 1.0 if every claim in the ANSWER can be directly supported by the CONTEXT.
- Score 0.0 if the ANSWER contains information not present in the CONTEXT (hallucination).
- Use values between 0 and 1 for partial faithfulness.

Respond with ONLY a decimal number between 0 and 1. Example: 0.8"""
    raw = call_llm(prompt, max_tokens=10)
    return parse_score(raw)


def score_answer_relevance(question: str, answer_ai: str) -> Optional[float]:
    """
    Answer Relevance: Câu trả lời AI có thực sự trả lời đúng câu hỏi không?
    Điểm 1.0 = hoàn toàn liên quan.
    """
    prompt = f"""You are an expert evaluator. Rate how relevant the answer is to the question.

QUESTION:
{question}

ANSWER:
{answer_ai[:800]}

Instructions:
- Score 1.0 if the answer directly and completely addresses the question.
- Score 0.0 if the answer is completely irrelevant to the question.
- Use values between 0 and 1 for partial relevance.

Respond with ONLY a decimal number between 0 and 1. Example: 0.9"""
    raw = call_llm(prompt, max_tokens=10)
    return parse_score(raw)


def score_context_recall(context: str, ground_truth: str) -> Optional[float]:
    """
    Context Recall: Context retrieved có chứa đủ thông tin để suy ra ground truth không?
    Điểm 1.0 = context đủ để trả lời hoàn toàn.
    """
    prompt = f"""You are an expert evaluator. Assess how well the retrieved context supports the ground truth answer.

CONTEXT:
{context[:2000]}

GROUND TRUTH ANSWER:
{ground_truth[:500]}

Instructions:
- Score 1.0 if the context contains ALL information needed to arrive at the ground truth.
- Score 0.0 if the context is completely missing relevant information.
- Use values between 0 and 1 for partial recall.

Respond with ONLY a decimal number between 0 and 1. Example: 0.7"""
    raw = call_llm(prompt, max_tokens=10)
    return parse_score(raw)


def score_context_precision(question: str, context: str, ground_truth: str) -> Optional[float]:
    """
    Context Precision: Context retrieved có bị dư thừa/nhiễu không?
    Điểm 1.0 = context rất chính xác, không có thông tin nhiễu.
    """
    prompt = f"""You are an expert evaluator. Assess how precise the retrieved context is for answering the question.

QUESTION:
{question}

CONTEXT:
{context[:2000]}

GROUND TRUTH ANSWER:
{ground_truth[:500]}

Instructions:
- Score 1.0 if the context contains ONLY relevant, useful information with no noise.
- Score 0.0 if the context is mostly irrelevant noise.
- Use values between 0 and 1 based on the signal-to-noise ratio.

Respond with ONLY a decimal number between 0 and 1. Example: 0.6"""
    raw = call_llm(prompt, max_tokens=10)
    return parse_score(raw)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    logger.info("=" * 60)
    logger.info("  RAGAS-style Evaluation")
    logger.info(f"  Input : {INPUT_CSV}")
    logger.info(f"  Output: {OUTPUT_CSV}")
    logger.info("=" * 60)

    if not INPUT_CSV.exists():
        logger.error(f"File không tồn tại: {INPUT_CSV}")
        sys.exit(1)

    df = pd.read_csv(INPUT_CSV, encoding="utf-8-sig")
    if MAX_SAMPLES:
        df = df.head(MAX_SAMPLES)

    total = len(df)
    logger.info(f"Tổng số mẫu cần đánh giá: {total}")

    results = []
    for i, row in df.iterrows():
        idx         = i + 1
        question    = str(row.get("question", ""))
        context     = str(row.get("documents", ""))
        ground_truth= str(row.get("response", ""))
        answer_ai   = str(row.get("response_AI", ""))
        sim_score   = row.get("similarity_score", "")
        true_false  = row.get("true_false", "")

        logger.info(f"[{idx}/{total}] Đang đánh giá: {question[:80]}...")

        faith  = score_faithfulness(question, context, answer_ai)
        time.sleep(BATCH_PAUSE)
        ans_rel = score_answer_relevance(question, answer_ai)
        time.sleep(BATCH_PAUSE)
        ctx_rec = score_context_recall(context, ground_truth)
        time.sleep(BATCH_PAUSE)
        ctx_pre = score_context_precision(question, context, ground_truth)
        time.sleep(BATCH_PAUSE)

        # Tính RAGAS Score tổng hợp (harmonic mean của 4 metrics)
        scores = [s for s in [faith, ans_rel, ctx_rec, ctx_pre] if s is not None]
        ragas_total = round(float(np.mean(scores)), 4) if scores else None

        results.append({
            "question":            question,
            "ground_truth":        ground_truth,
            "response_AI":         answer_ai,
            "cosine_similarity":   sim_score,
            "cosine_true_false":   true_false,
            "faithfulness":        faith,
            "answer_relevance":    ans_rel,
            "context_recall":      ctx_rec,
            "context_precision":   ctx_pre,
            "ragas_score":         ragas_total,
        })

        logger.info(
            f"  → Faithfulness={faith}  AnswerRel={ans_rel}  "
            f"CtxRecall={ctx_rec}  CtxPrecision={ctx_pre}  "
            f"RAGAS={ragas_total}"
        )

    # Lưu kết quả
    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    out_df = pd.DataFrame(results)
    out_df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")

    # Tóm tắt
    logger.info("\n" + "=" * 60)
    logger.info(f"Kết quả lưu tại: {OUTPUT_CSV}")
    logger.info(f"Tổng mẫu        : {total}")
    for col in ["faithfulness", "answer_relevance", "context_recall", "context_precision", "ragas_score"]:
        valid = out_df[col].dropna()
        if not valid.empty:
            logger.info(f"Avg {col:<22}: {valid.mean():.4f}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
