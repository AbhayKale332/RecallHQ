FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY migrations ./migrations
COPY data/synthetic/story.yaml data/synthetic/corpus.jsonl ./data/synthetic/
RUN pip install --no-cache-dir .
EXPOSE 8001
CMD ["uvicorn", "recallhq.api:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
