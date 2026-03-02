FROM python:3.11-slim

WORKDIR /app

# Системные зависимости для asyncpg и pgvector
RUN apt-get update --fix-missing && apt-get install -y --fix-missing \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --only main --no-root

COPY . .

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]