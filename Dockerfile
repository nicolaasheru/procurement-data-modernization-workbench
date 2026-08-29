FROM python:3.12-slim AS runtime

ARG EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface \
    EMBEDDING_MODEL=${EMBEDDING_MODEL} \
    EMBEDDING_DIMENSIONS=384 \
    PORT=8000

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt backend/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install -r backend/requirements.txt

# Cache the pinned model in the immutable image so startup does not depend on
# an external model download.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('${EMBEDDING_MODEL}')"

COPY backend backend
COPY data data
COPY scripts/start-backend.sh scripts/start-backend.sh
RUN chmod +x scripts/start-backend.sh \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app

USER appuser
EXPOSE 8000
CMD ["/app/scripts/start-backend.sh"]
