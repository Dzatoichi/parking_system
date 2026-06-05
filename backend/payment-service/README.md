# Payment Service

Mock payment and fine service for the parking system MVP.

## Endpoints

- `POST /payments` creates a pending mock payment.
- `POST /payments/{payment_id}/confirm` marks payment as succeeded.
- `POST /payments/{payment_id}/fail` marks payment as failed.
- `POST /payments/{payment_id}/cancel` cancels payment.
- `POST /payments/{payment_id}/refund` refunds succeeded payment.
- `POST /webhooks/mock` simulates provider webhook by `provider_payment_id`.
- `POST /fines` creates a fine.
- `POST /fines/{fine_id}/pay` creates a payment for a fine.
- `GET /payment-events` returns payment/fine event journal.
