# Интеллектуальная система управления паркингом

Распределённая микросервисная система для автоматизации управления парковкой с применением компьютерного зрения. Система обеспечивает автоматическое распознавание номерных знаков, трекинг автомобилей между камерами, мониторинг занятости мест в реальном времени и аналитику через веб-интерфейс.

---

## Содержание

- [Возможности](#-возможности)
- [Архитектура](#-архитектура)
- [Стек технологий](#-стек-технологий)
- [Структура проекта](#-структура-проекта)
- [Быстрый старт](#-быстрый-старт)
- [Сервисы и порты](#-сервисы-и-порты)
- [API документация](#-api-документация)
- [Команда](#-команда)

---

## Возможности

- **Распознавание номерных знаков** — автоматическая идентификация автомобиля при въезде/выезде через нейросетевую модель
- **Трекинг автомобилей** — сквозное отслеживание перемещения по территории парковки с помощью embeddings между камерами
- **Мониторинг мест** — детекция занятости каждого парковочного места в реальном времени с привязкой к автомобилю
- **Поиск автомобилей** — поиск по номеру, просмотр маршрута и видеоархива визита
- **Аналитика** — отчёты о загрузке по часам/дням/неделям, статистика выручки
- **Веб-интерфейс** — панель управления с картой парковки, сетью камер и настройками

---

## Архитектура

Система построена на принципах микросервисной архитектуры. Каждый сервис независим, взаимодействует с остальными через HTTP API.

```
                        ┌─────────────────┐
                        │   Frontend      │
                        │  React + Vite   │
                        │   :3000 → :80   │
                        └────────┬────────┘
                                 │
                        ┌────────▼────────┐
                        │   API Gateway   │
                        │     Nginx       │
                        └──┬──────┬──┬───┘
                           │      │  │
           ┌───────────────┘      │  └──────────────────┐
           │                      │                     │
  ┌────────▼──────────┐  ┌────────▼────────┐  ┌────────▼────────┐
  │ parking-management│  │ cv-processing   │  │  analytics      │
  │     -service      │  │    -service     │  │   -service      │
  │  FastAPI  :8000   │  │  FastAPI :8001  │  │  FastAPI :????  │
  └────────┬──────────┘  └────────▲────────┘  └─────────────────┘
           │                      │
  ┌────────▼──────────┐  ┌────────┴────────┐
  │   PostgreSQL      │  │ stream-ingest   │
  │     :5432         │  │    -service     │
  └───────────────────┘  │  FastAPI :8002  │
                         └─────────────────┘
```

### Сервисы

| Сервис | Назначение |
|--------|-----------|
| `parking-management-service` | Основная бизнес-логика: управление въездом/выездом, история парковок, поиск |
| `cv-processing-service` | Обработка CV-задач: запуск нейросетевых моделей, распознавание номеров, embeddings |
| `stream-ingest-service` | Приём и маршрутизация видеопотоков с камер (RTSP) в cv-processing |
| `analytics-service` | Аналитика и отчёты по загрузке и статистике парковки |
| `api-gateway` | Nginx reverse proxy — единая точка входа для фронтенда |
| `frontend` | React SPA — веб-интерфейс оператора |

---

## Стек технологий

**Backend**
- Python 3.11 + FastAPI + Uvicorn
- PostgreSQL 15
- Docker / Docker Compose

**Frontend**
- React + TypeScript
- TanStack Query (react-query)
- Nginx (для продакшн-сборки)

**ML / CV**
- Нейросети для детекции и распознавания номерных знаков
- Embedder-модель для извлечения признаков автомобилей
- Поддержка видеопотоков по протоколу RTSP

---

## Структура проекта

```
.
├── docker-compose.yml
├── frontend/
│   └── src/
│       ├── Dockerfile
│       ├── App.tsx
│       └── components/
│           ├── Dashboard.tsx        # Главная панель
│           ├── ParkingMap.tsx       # Карта парковки
│           ├── Analytics.tsx        # Аналитика
│           ├── Settings.tsx         # Настройки
│           ├── cameras-network/     # Управление сетью камер
│           └── parking-marker/      # Разметка парковочных мест
└── backend/
    ├── parking-management-service/
    │   ├── Dockerfile
    │   ├── .env
    │   └── src/
    ├── cv-processing-service/
    │   ├── Dockerfile
    │   ├── pyproject.toml
    │   └── src/
    │       └── api/
    │           ├── routers/
    │           └── repositories/
    ├── stream-ingest-service/
    │   ├── Dockerfile
    │   └── src/
    ├── analytics-service/
    │   ├── Dockerfile
    │   └── src/
    └── api-gateway/
        └── nginx.conf
```

---

## Быстрый старт

### Требования

- [Docker](https://docs.docker.com/get-docker/) 24+
- [Docker Compose](https://docs.docker.com/compose/) v2+

### Установка и запуск

1. Клонируй репозиторий:
```bash
git clone https://github.com/your-username/parking-management-system.git
cd parking-management-system
```

2. Создай `.env` файл для `parking-management-service`:
```bash
cp backend/parking-management-service/.env.example backend/parking-management-service/.env
# Отредактируй значения при необходимости
```

3. Запусти все сервисы:
```bash
docker compose up --build
```

4. Открой веб-интерфейс: [http://localhost:3000](http://localhost:3000)

### Остановка

```bash
docker compose down

# Удалить вместе с данными БД:
docker compose down -v
```

---

## 🔌 Сервисы и порты

| Сервис | Порт | URL |
|--------|------|-----|
| Frontend | 3000 | http://localhost:3000 |
| parking-management-service | 8000 | http://localhost:8000 |
| cv-processing-service | 8001 | http://localhost:8001 |
| stream-ingest-service | 8002 | http://localhost:8002 |
| PostgreSQL | 5432 | localhost:5432 |

### Health checks

```bash
curl http://localhost:8000/health   # parking-management-service
curl http://localhost:8001/health   # cv-processing-service
curl http://localhost:8002/health   # stream-ingest-service
```

---

## API документация

После запуска интерактивная Swagger-документация доступна по адресам:

- **parking-management-service**: http://localhost:8000/docs
- **cv-processing-service**: http://localhost:8001/docs
- **stream-ingest-service**: http://localhost:8002/docs

### Пример: создать задачу на обработку видеопотока

```bash
curl -X POST http://localhost:8001/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "camera_id": "cam-01",
    "stream_url": "rtsp://192.168.1.10:554/stream",
    "options": {}
  }'
```

---

## Команда

| Участник | Роль |
|----------|------|
| Каштанов Данила Владимирович | Руководитель проекта |
| Коптев Сергей Андреевич | Разработчик |
| Коптев Алексей Андреевич | Разработчик |
