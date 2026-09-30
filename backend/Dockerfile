FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
# No --workers flag: uvicorn reads WEB_CONCURRENCY (default 1). Multiple
# workers are safe now that chats live in Redis and vectors in Pinecone.
# The Celery worker reuses this image with its own command (docker-compose.yml).
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
