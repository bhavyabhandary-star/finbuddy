# RAG-grounded WhatsApp coach service (retriever + Groq generation).
#
# Build context is THIS DIRECTORY (rag_service/), not the repo root --
# deliberately, so this directory is self-contained and can be pushed as-is
# to its own HuggingFace Space via `git subtree push --prefix=rag_service`,
# where it becomes that Space's repo root. Build/run locally with:
#   docker build -t finbuddy-rag -f rag_service/Dockerfile rag_service/
#
# See scoring_service/Dockerfile for why Python 3.14.
FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copied into a `rag_service` subdirectory so `from rag_service.X import Y`
# resolves correctly inside the image.
COPY . ./rag_service/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8002

# DATABASE_URL and GROQ_API_KEY are injected as environment variables at
# container runtime -- never baked into the image. See .env.example.
CMD ["uvicorn", "rag_service.main:app", "--host", "0.0.0.0", "--port", "8002"]
