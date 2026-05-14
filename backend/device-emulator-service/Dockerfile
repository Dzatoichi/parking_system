FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN mkdir -p /app/data

RUN pip install --no-cache-dir \
    "fastapi>=0.115.0,<0.130.0" \
    "uvicorn[standard]>=0.30.0,<0.41.0" \
    "sqlalchemy[asyncio]>=2.0.30,<3.0.0" \
    "aiosqlite>=0.20.0,<1.0.0" \
    "pydantic-settings>=2.0,<3.0"

COPY src ./src

EXPOSE 8004

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8004", "--reload"]
