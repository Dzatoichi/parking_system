# Notification Service

Push notification service for the parking system MVP.

## Endpoints

- `POST /devices/register` stores a mobile/web push token.
- `POST /devices/unregister` disables a push token.
- `POST /notifications` creates and sends a notification.
- `POST /notifications/from-event` creates a notification from a known event type.
- `POST /notifications/test` sends a test notification.
- `GET /notifications/user/{user_id}` returns notification history.

## Real push setup

The service sends real mobile push notifications through Firebase Cloud Messaging HTTP v1 when:

- `PUSH_PROVIDER=fcm`
- `FCM_PROJECT_ID=<firebase-project-id>`
- `FCM_SERVICE_ACCOUNT_FILE=/app/secrets/firebase-service-account.json`

Mount the Firebase service account JSON into `/app/secrets/firebase-service-account.json`.
Use `PUSH_PROVIDER=mock` only for local demos without Firebase credentials.
