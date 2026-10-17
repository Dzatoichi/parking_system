# PostgreSQL persistence for the parking controller

The main controller uses `DB/parking_repository.py`. It stores identities, OCR reads,
sampled Re-ID embeddings and movement/topology events. Embeddings are JSONB arrays for
now; **pgvector is not required**. This is deliberately compatible with PostgreSQL-like
servers that implement the PostgreSQL wire protocol and JSONB.

## Environment

Set these before starting `run_main_controller.py`:

- `PARKING_DB_HOST` — default `127.0.0.1`
- `PARKING_DB_PORT` — default `5432`
- `PARKING_DB_NAME` — default `parking_db`
- `PARKING_DB_USER` — default `tracklet_manager`
- `PARKING_DB_PASSWORD` — default `tracklet_manager`
- `PARKING_DB_CONNECT_TIMEOUT` — default `5` seconds
- `PARKING_DB_ENABLED=false` — explicit opt-out for code-only debugging

The repository creates its tables and indexes automatically at startup. Use a dedicated
development database; do not point a soak test at production data unless that is intended.
Database errors are not silently ignored when persistence is enabled.

## PostgreSQL emulator on Windows

You may be thinking of **PGlite** (an embedded PostgreSQL build compiled to WebAssembly)
or **pg-mem** (an in-memory PostgreSQL emulator). They are not interchangeable:

- The Python controller uses `psycopg2`, which expects a PostgreSQL wire-protocol TCP
  endpoint. A PGlite instance needs a compatible server/socket bridge to be reachable at
  `PARKING_DB_HOST:PARKING_DB_PORT`.
- `pg-mem` is primarily an in-process JavaScript emulator and is not a drop-in TCP server
  for this Python process.

If your emulator exposes a normal PostgreSQL connection endpoint, configure its host,
port, database, user and password above. No pgvector extension is used.

## Tables

- `parking_vehicle`: stable `global_id`, latest plate, status and scan source.
- `parking_plate_read`: individual OCR readings and confidence values.
- `parking_embedding`: normalized embedding vectors stored as JSONB.
- `parking_track_event`: registration, movement, scan-zone binding, topology exits and Re-ID matches.

Embedding writes are buffered in batches of 100 to avoid a commit for every sample.
