FROM python:3.11-slim

WORKDIR /app

# Системные зависимости для asyncpg и pgvector
RUN apt-get update --fix-missing && apt-get install -y --fix-missing \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --only main --no-root

# Установка watchfiles для быстрого hot reload
RUN pip install watchfiles

COPY . .

# Создаем два entrypoint скрипта - для production и development
RUN printf '#!/bin/sh\nset -e\necho "Running migrations..."\nalembic upgrade head\necho "Starting app..."\nexec uvicorn src.main:app --host 0.0.0.0 --port 8000\n' > /entrypoint.sh \
    && chmod +x /entrypoint.sh

RUN printf '#!/bin/sh\nset -e\necho "Running migrations..."\nalembic upgrade head\necho "Starting app in development mode with hot reload..."\nexec uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload\n' > /entrypoint-dev.sh \
    && chmod +x /entrypoint-dev.sh

EXPOSE 8000

# Используем production entrypoint по умолчанию
CMD ["/entrypoint-dev.sh"]