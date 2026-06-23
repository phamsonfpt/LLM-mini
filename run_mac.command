#!/bin/bash

# ==============================================================================
# NotebookLM-Mini 1-Click Run Script cho macOS (Zero-Dependency)
# ==============================================================================

set -e

echo "🚀 Khởi động NotebookLM-Mini cho macOS..."
cd "$(dirname "$0")"

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Cài đặt các công cụ hệ thống cần thiết qua Homebrew (Chỉ cài nếu có sẵn brew)
if command_exists brew; then
    if ! command_exists ffmpeg; then
        echo "📦 Đang cài đặt ffmpeg (để xử lý âm thanh)..."
        brew install ffmpeg
    fi
    if ! command_exists tesseract; then
        echo "📦 Đang cài đặt Tesseract OCR (để nhận diện chữ trong ảnh)..."
        brew install tesseract tesseract-lang
    fi
fi

# 2. Kiểm tra và cài đặt uv (Trình quản lý package siêu tốc)
if ! command_exists uv; then
    echo "📦 Đang cài đặt uv (Công cụ quản lý môi trường siêu tốc)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

# 3. Khởi tạo môi trường ảo bằng Python 3.11 Portable (Không cần cài Python trên máy)
if [ ! -d ".venv" ]; then
    echo "🛠 Đang tạo môi trường ảo Python hoàn toàn độc lập..."
    uv python install 3.11
    uv venv --python 3.11
    
    # 4. Kích hoạt môi trường ảo
    source .venv/bin/activate

    # 5. Cài đặt các thư viện lõi
    echo "📥 Đang đồng bộ hóa thư viện..."
    uv pip install -r requirements.txt

    # 6. Cài đặt llama-cpp-python với cờ Metal cho Mac M-series (tối ưu tốc độ)
    echo "⚡ Đang kiểm tra/cài đặt Engine AI tối ưu cho máy Mac..."
    if ! python -c "import llama_cpp" 2>/dev/null; then
        echo "🚀 Cài đặt Llama.cpp với cấu hình Apple Metal GPU..."
        CMAKE_ARGS="-DGGML_METAL=on" uv pip install llama-cpp-python --no-cache-dir
    fi

    # 6.5 Quét phần cứng và tự động cài đặt Model Zoo
    echo "🔍 Đang quét cấu hình máy tính của bạn để đề xuất Model AI tối ưu..."
    python src/utils/hardware_profiler.py
else
    echo "ℹ️ Môi trường ảo .venv đã tồn tại. Bỏ qua đồng bộ hóa thư viện (Hỗ trợ chạy Offline)."
    # Kích hoạt môi trường ảo
    source .venv/bin/activate
fi

# 6.6 Tự động build Frontend nếu chưa có bản dựng (Vấn đề số 4)
if [ ! -d "frontend/dist" ]; then
    echo "📦 Không tìm thấy bản dựng frontend/dist. Đang tự động build giao diện..."
    if command_exists npm; then
        cd frontend
        npm install
        npm run build
        cd ..
    else
        echo "⚠️ Cảnh báo: Không tìm thấy npm (Node.js) trên máy. Giao diện web sẽ không hiển thị được."
    fi
fi

# 7. Khởi động hệ thống
echo "✨ Bắt đầu chạy hệ thống..."
echo "-> Mở trình duyệt Web tại: http://127.0.0.1:8000"

# Đợi 2 giây cho Server Uvicorn khởi động, sau đó mở web
(sleep 3 && open http://127.0.0.1:8000) &

# Cấu hình VRAM swap tối ưu cho macOS (tránh OOM trên máy 8GB RAM)
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=0.0

# Chạy Backend (sẽ tự phát Frontend nếu đã build)
uvicorn src.api.api:app --host 127.0.0.1 --port 8000
