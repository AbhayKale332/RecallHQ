FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv
WORKDIR /app
ENV PYTHONPATH=/app/src
ENV PATH=/app/.venv/bin:$PATH
ENV TIKTOKEN_CACHE_DIR=/app/.cache/tiktoken
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY migrations ./migrations
COPY data/synthetic/story.yaml data/synthetic/corpus.jsonl ./data/synthetic/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-editable
RUN python -c "import tiktoken; tiktoken.get_encoding('o200k_base')"
EXPOSE 8001
CMD ["uvicorn", "recallhq.api:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
