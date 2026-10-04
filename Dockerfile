# ============================================================
# 🐳 Dockerfile — App luyện đọc (Tiếng Anh + Tiếng Trung)
#
# Build context = THƯ MỤC GỐC dự án (nơi chứa index.html, index_trung.html
# và thư mục python_backend/). Khi deploy trên Render/Railway chỉ cần trỏ
# Dockerfile về file này, KHÔNG cần cấu hình gì thêm.
#
# Chạy thử ở máy local:
#   docker build -t app-luyen-doc .
#   docker run -p 8000:8000 -e GEMINI_API_KEY=xxx app-luyen-doc
#   -> mở http://127.0.0.1:8000
# ============================================================
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# 1) Thư viện hệ thống: Tesseract OCR (kèm gói tiếng Anh + Trung giản/phồn)
#    và các thư viện C mà OpenCV/PyMuPDF cần.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-chi-sim \
        tesseract-ocr-chi-tra \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) Cài Python packages TRƯỚC (tận dụng cache layer, build lại nhanh hơn)
COPY python_backend/requirements.txt /app/python_backend/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /app/python_backend/requirements.txt \
    && python -m spacy download en_core_web_sm

# 3) Copy toàn bộ backend (code + dữ liệu JSON/CSV + CSV CEFR đã đặt cạnh code)
COPY python_backend/ /app/python_backend/

# 4) Copy 2 trang giao diện vào /app/public
#    -> main.py sẽ tự phục vụ chúng tại "/" (cùng tên miền với API)
RUN mkdir -p /app/public
COPY index.html /app/public/index.html
COPY index_trung.html /app/public/index_trung.html

WORKDIR /app/python_backend

# Render/Railway tự cấp biến PORT; khi chạy `docker run` mà không set thì mặc định 8000.
EXPOSE 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
