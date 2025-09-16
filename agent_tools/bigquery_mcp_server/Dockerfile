# Dockerfile
FROM python:3.11-slim

# Avoid buffering stdout/stderr (helps logs/streaming)
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy app
COPY . .

# expose default port (informational)
EXPOSE 8080

# Cloud Run provides PORT env var; just run the server
CMD ["python", "server.py"]
