import os
from typing import Optional, List, Dict

from ..document_tree import DocumentNode, HeadingNode, ParagraphNode

class AudioParser:
    """Parser xử lý file âm thanh (MP3, WAV) sử dụng faster-whisper (hỗ trợ Python 3.8-3.13).
    
    faster-whisper nhanh hơn openai-whisper gốc ~4x và không yêu cầu numba/llvmlite,
    do đó tương thích hoàn toàn với Python 3.13+.
    """

    def __init__(self, model_size: str = "base"):
        self.model_size = model_size
        self.model = None

    def _load_model(self):
        if self.model is None:
            try:
                from src.utils.vram_orchestrator import get_orchestrator
                print(f"[AudioParser] Đang tải mô hình Whisper ({self.model_size}) qua Orchestrator...")
                self.model = get_orchestrator().get_whisper(self.model_size)
                if self.model is None:
                    raise RuntimeError("Không thể tải model Whisper thông qua VRAM Orchestrator.")
            except ImportError:
                # Fallback nếu orchestrator chưa có
                from faster_whisper import WhisperModel
                print(f"[AudioParser] Đang tải mô hình Whisper ({self.model_size}) trực tiếp...")
                self.model = WhisperModel(self.model_size, device="auto", compute_type="int8")
            except Exception as e:
                raise RuntimeError(
                    f"Lỗi khởi tạo Whisper model: {e}\n"
                    "(Bạn đã cài đặt ffmpeg trên máy chưa?)"
                )

    def unload(self):
        """Xả mô hình Whisper khỏi bộ nhớ thông qua Orchestrator."""
        try:
            from src.utils.vram_orchestrator import get_orchestrator
            get_orchestrator().release_whisper()
        except ImportError:
            pass
        self.model = None

    def _group_segments_into_paragraphs(self, segments, max_duration: float = 30.0) -> List[Dict]:
        """Gộp các đoạn âm thanh ngắn thành các đoạn văn dài hơn."""
        paragraphs = []
        current_text = []
        current_start = 0.0

        segments_list = list(segments)  # faster-whisper trả về generator, cần convert thành list
        if not segments_list:
            return paragraphs

        current_start = segments_list[0].start

        for seg in segments_list:
            text = seg.text.strip()
            if text:
                current_text.append(text)
            current_duration = seg.end - current_start

            if current_duration >= max_duration:
                paragraphs.append({
                    'text': " ".join(current_text).replace('\n', ' '),
                    'start': current_start,
                    'end': seg.end
                })
                current_text = []
                current_start = seg.end

        if current_text:
            last_end = segments_list[-1].end if segments_list else current_start
            paragraphs.append({
                'text': " ".join(current_text).replace('\n', ' '),
                'start': current_start,
                'end': last_end
            })

        return paragraphs

    def parse(self, audio_path: str, source_metadata: Optional[dict] = None) -> DocumentNode:
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Không tìm thấy file audio: {audio_path}")

        self._load_model()

        print(f"[AudioParser] Đang bóc băng âm thanh (Transcribing): {os.path.basename(audio_path)}")
        try:
            # faster-whisper trả về (segments_generator, info)
            segments_gen, info = self.model.transcribe(audio_path, beam_size=5, language=None)
            detected_language = info.language
            
            # Phải consume generator TRƯỚC KHI unload model
            paragraphs = self._group_segments_into_paragraphs(segments_gen, max_duration=45.0)
        except Exception as e:
            raise RuntimeError(f"Lỗi khi transcribe audio (kiểm tra xem ffmpeg đã được cài chưa): {e}")
        finally:
            # === MEMORY OPTIMIZATION ===
            # Giải phóng Whisper ngay sau khi transcribe xong để trả lại ~1GB RAM
            self.unload()

        # Xây dựng metadata
        meta = source_metadata or {}
        meta["source_file"] = os.path.basename(audio_path)
        meta["parser"] = "AudioParser"
        meta["language"] = detected_language

        # Khởi tạo Document Tree
        doc_node = DocumentNode(metadata=meta)
        doc_node.add_child(HeadingNode(level=1, content=f"Audio Transcript: {os.path.basename(audio_path)}"))

        for p in paragraphs:
            p_meta = {
                "timestamp_start": round(p['start'], 2),
                "timestamp_end": round(p['end'], 2),
                "timestamp_display": f"[{int(p['start']//60):02d}:{int(p['start']%60):02d} - {int(p['end']//60):02d}:{int(p['end']%60):02d}]"
            }
            content = f"{p_meta['timestamp_display']} {p['text']}"
            doc_node.add_child(ParagraphNode(content=content, metadata=p_meta))

        return doc_node
