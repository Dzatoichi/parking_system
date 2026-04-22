FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir \
    asyncpg \
    bcrypt \
    email-validator \
    fastapi \
    pydantic \
    pydantic-settings \
    PyJWT \
    sqlalchemy \
    uvicorn \
    watchfiles

COPY . .

EXPOSE 8003

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8003", "--reload"]
