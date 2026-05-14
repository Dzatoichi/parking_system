# Device Emulator Service

Эмуляция внешних устройств парковки (шлагбаум, освещение) и журнал интеграционных событий (FT‑6 на уровне стенда).

## Запуск локально

Из каталога сервиса (один и тот же интерпретатор для pip и uvicorn):

```bash
cd backend/device-emulator-service
mkdir -p data   # Windows: mkdir data
python -m pip install -r requirements.txt
python -m uvicorn src.main:app --reload --host 127.0.0.1 --port 8004
```

На Windows не смешивайте голый `pip` и `python` из разных установок — используйте **`python -m pip`**.

## API

- `GET /health`
- `GET /v1/parking/{parking_id}/devices/state` — текущее состояние эмуляторов
- `POST /v1/parking/{parking_id}/devices/barrier/open?simulate_unreachable=false`
- `POST /v1/parking/{parking_id}/devices/barrier/close`
- `POST /v1/parking/{parking_id}/devices/lighting` — тело: `{"on": true, "brightness": 80, "simulate_unreachable": false}`
- `GET /v1/parking/{parking_id}/devices/events?page=1&size=50`

Данные хранятся в SQLite (`./data/emulator.db`, путь задаётся через `SQLITE_PATH` в `.env`).

## Docker

Сервис поднимается из корня репозитория: `docker compose up device-emulator-service`.

Фронтенд проксирует префикс `/emulator` на этот сервис (см. `vite.config.ts` и переменную `VITE_EMULATOR_PROXY_TARGET`).
