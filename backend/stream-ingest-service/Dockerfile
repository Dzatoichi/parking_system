FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml poetry.lock* ./
RUN pip install --no-cache-dir poetry watchfiles && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-root

COPY . .

EXPOSE 8002

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8002", "--reload"]
