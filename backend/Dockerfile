FROM python:3.11-slim

WORKDIR /app

# Install dependencies first so the layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Persisted slices and the audit journal live here; the compose file mounts a
# volume over it so they survive a container restart.
RUN mkdir -p /data
ENV HELIX_DATABASE_PATH=/data/helix.db \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
