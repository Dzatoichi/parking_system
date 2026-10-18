# Vehicle search integration contract

This is a transport-neutral boundary for the backend/broker team. No broker vendor
is selected here; the colleague implementing transport supplies a small adapter.

## Start

- Standalone existing mode: `python run_main_controller.py`
- Integration entry point: `PARKING_INTEGRATION_MODE=1 python -m IntegrationModule.entrypoint`
- Optional adapter class: `PARKING_BROKER_ADAPTER=package.module:AdapterClass`

The adapter class implements:

- `consume(stop_event)` — yields decoded inbound message dictionaries until stopped.
- `publish(event)` — publishes an outbound event dictionary.
- `close()` — closes broker resources.

Without `PARKING_BROKER_ADAPTER`, a no-network stub is used. It accepts no inbound
messages and prints outbound messages, so it is only for smoke testing.

## Inbound request

```json
{
  "event": "vehicle_search_request",
  "search_id": "search-2026-001",
  "plates": ["AB123CD", "XY987ZT"]
}
```

`search_id` is the idempotency key. Different IDs can be active concurrently.
Repeated delivery of the same ID does not create a duplicate request. A repeated ID
with a different plate list replaces that request's current list. `license_plates`
is accepted as an alternate field name.

## Outbound notification

```json
{
  "event": "vehicle_found",
  "schema_version": 1,
  "search_id": "search-2026-001",
  "plate": "AB123CD",
  "journey_id": 42,
  "camera_id": 1,
  "zone": "LEFT",
  "local_track_id": 17,
  "timestamp": "2026-10-18T12:00:00+00:00"
}
```

## OCR decision rule

The shared registry exposes the exact decision rule for the controller integration:
OCR must have **more than 5 votes** and mean OCR character confidence **strictly greater
than 0.95**. Until then the decision is `PENDING`; after the threshold it is `MATCH`
if the plate is in any active request, otherwise `REJECT`. This file defines the
contract; controller-side provisional collection/cleanup must be wired to these hooks
before enabling the integration in production.
