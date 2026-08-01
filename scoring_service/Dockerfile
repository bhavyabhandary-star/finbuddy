# F-001/003/006/012 + Risk-Trend + F-007/9 scoring service.
#
# Build context is THIS DIRECTORY (scoring_service/), not the repo root --
# deliberately, so this directory is self-contained and can be pushed as-is
# to its own HuggingFace Space via `git subtree push --prefix=scoring_service`,
# where it becomes that Space's repo root. Build/run locally with:
#   docker build -t finbuddy-scoring -f scoring_service/Dockerfile scoring_service/
#
# Python 3.14 to match what was actually developed and tested against --
# this machine's Application Control policy blocks numba/llvmlite locally
# (why F-003 uses XGBoost's native Tree SHAP instead of the `shap`
# package), which is a local-machine constraint, not a Docker/Linux one,
# but the code was built and verified on 3.14 so the image matches it
# rather than introducing an untested Python version at deploy time.
FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copied into a `scoring_service` subdirectory (not flat at /app) so
# `from scoring_service.X import Y` -- exactly how every module in this
# codebase imports -- resolves correctly inside the image.
COPY . ./scoring_service/

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

EXPOSE 8001

# Secrets (SETU_*, etc.) are injected as environment variables at container
# runtime by the deploy target (HF Spaces "Secrets" / ECS task env) -- never
# baked into the image. See .env.example for the full list.
CMD ["uvicorn", "scoring_service.api.main:app", "--host", "0.0.0.0", "--port", "8001"]
