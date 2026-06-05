FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 libxcb1 libx11-6 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

# Устанавливаем зависимости по одному (чтобы видеть где ошибка)
RUN pip install --no-cache-dir fastapi uvicorn pydantic pydantic-settings httpx aio-pika psycopg2-binary

RUN pip install --no-cache-dir numpy==1.26.4

RUN pip install --no-cache-dir opencv-python-headless

RUN pip install --no-cache-dir torch==2.6.0 torchvision==0.21.0 --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir ultralytics==8.3.0 "lapx>=0.5.2"

COPY . .

EXPOSE 8001

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001"]
