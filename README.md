# parking_system

## Stream ingest wrapper over CV processing

Added services:
- `cv-processing-service` (`http://localhost:8001`) - CV API with job lifecycle endpoints.
- `stream-ingest-service` (`http://localhost:8002`) - ingest facade that wraps CV API.

Both services now use layered architecture like `parking-management-service`:
- `routers` (HTTP layer)
- `services` (business logic)
- `repositories` (data access; currently in-memory)
- `schemas` (request/response DTO)
- `utils/dependencies.py` (DI composition)
- `settings/config.py` (configuration)

`stream-ingest-service` endpoints:
- `POST /v1/ingest/streams` - starts ingest + creates CV job.
- `GET /v1/ingest/streams/{ingest_id}` - returns aggregated ingest status.
- `POST /v1/ingest/streams/{ingest_id}/stop` - stops ingest and underlying CV job.

## How to run

```bash
docker compose up --build
```

## Quick check

Start ingest:
```bash
curl -X POST http://localhost:8002/v1/ingest/streams \
  -H "Content-Type: application/json" \
  -d "{\"camera_id\":\"cam-1\",\"stream_url\":\"rtsp://example.local/stream\"}"
```

Get status:
```bash
curl http://localhost:8002/v1/ingest/streams/<ingest_id>
```

Stop ingest:
```bash
curl -X POST http://localhost:8002/v1/ingest/streams/<ingest_id>/stop
```

## How to integrate in the system

1. Route all new stream start/stop calls from UI or gateway to `stream-ingest-service`, not directly to CV.
2. Keep `cv-processing-service` internal and use it only via `stream-ingest-service`.
3. Connect real CV pipeline in service layer:
   - `backend/cv-processing-service/src/services/cv_job_service.py`
   - replace stub create/stop behavior with real tracking/re-id orchestration.
4. Replace in-memory repositories with persistent DAO:
   - `backend/cv-processing-service/src/repositories/cv_job_repository.py`
   - `backend/stream-ingest-service/src/repositories/ingest_repository.py`
   - recommended storage: PostgreSQL + async DAO, same pattern as `parking-management-service`.
5. If you use API gateway (Nginx), add upstream routes:
   - `/api/ingest/* -> stream-ingest-service:8002`
   - optional internal `/api/cv/* -> cv-processing-service:8001`
