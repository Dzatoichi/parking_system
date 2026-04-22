FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update --fix-missing && apt-get install -y --fix-missing \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml poetry.lock* ./
RUN pip install --no-cache-dir poetry watchfiles && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-root

COPY . .

RUN printf '#!/bin/sh\nset -e\necho "Running migrations..."\nalembic upgrade head\necho "Starting app..."\nexec uvicorn src.main:app --host 0.0.0.0 --port 8000\n' > /entrypoint.sh && \
    chmod +x /entrypoint.sh

RUN printf '#!/bin/sh\nset -e\necho "Running migrations..."\nalembic upgrade head\necho "Starting app in development mode with hot reload..."\nexec uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload\n' > /entrypoint-dev.sh && \
    chmod +x /entrypoint-dev.sh

EXPOSE 8000

CMD ["/entrypoint-dev.sh"]
