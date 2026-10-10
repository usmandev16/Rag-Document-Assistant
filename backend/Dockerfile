FROM python:3.12-slim
WORKDIR /app
# Tesseract for the OCR fallback on PDF pages with no extractable text
# (src/loaders.py). It runs in the Celery worker, which uses this image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# No --workers flag: uvicorn reads WEB_CONCURRENCY (default 1). Multiple
# workers are safe now that chats live in Redis and vectors in Pinecone.
# The Celery worker reuses this image with its own command (docker-compose.yml).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
