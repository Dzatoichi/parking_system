from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"


@dataclass
class FCMDeliveryResult:
    success: bool
    provider_message_id: str | None = None
    error_message: str | None = None
    response_payload: dict[str, Any] | None = None


class FCMClient:
    def __init__(
        self,
        *,
        project_id: str | None,
        service_account_file: str,
        timeout_seconds: int = 10,
    ) -> None:
        self._project_id = project_id
        self._service_account_file = service_account_file
        self._timeout_seconds = timeout_seconds
        self._credentials = None

    async def send(
        self,
        *,
        token: str,
        title: str,
        body: str,
        data: dict[str, Any] | None = None,
    ) -> FCMDeliveryResult:
        config_error = self._validate_config()
        if config_error:
            return FCMDeliveryResult(success=False, error_message=config_error)

        access_token = await asyncio.to_thread(self._get_access_token)
        message = {
            "message": {
                "token": token,
                "notification": {
                    "title": title,
                    "body": body,
                },
                "data": self._stringify_data(data or {}),
                "android": {
                    "priority": "HIGH",
                    "notification": {
                        "channel_id": "parking_events",
                        "sound": "default",
                    },
                },
                "apns": {
                    "payload": {
                        "aps": {
                            "sound": "default",
                        }
                    }
                },
            }
        }
        url = f"https://fcm.googleapis.com/v1/projects/{self._project_id}/messages:send"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=message)
            payload = self._response_payload(response)
            if response.is_success:
                return FCMDeliveryResult(
                    success=True,
                    provider_message_id=payload.get("name"),
                    response_payload=payload,
                )
            return FCMDeliveryResult(
                success=False,
                error_message=f"FCM error {response.status_code}: {payload}",
                response_payload=payload,
            )
        except Exception as exc:
            return FCMDeliveryResult(success=False, error_message=f"FCM request failed: {exc}")

    def _validate_config(self) -> str | None:
        if not self._project_id:
            return "FCM_PROJECT_ID is not configured"
        if not self._service_account_file:
            return "FCM_SERVICE_ACCOUNT_FILE is not configured"
        if not Path(self._service_account_file).exists():
            return f"FCM service account file not found: {self._service_account_file}"
        return None

    def _get_access_token(self) -> str:
        from google.auth.transport.requests import Request
        from google.oauth2 import service_account

        if self._credentials is None:
            self._credentials = service_account.Credentials.from_service_account_file(
                self._service_account_file,
                scopes=[FCM_SCOPE],
            )
        if not self._credentials.valid or self._credentials.expired:
            self._credentials.refresh(Request())
        return self._credentials.token

    @staticmethod
    def _stringify_data(data: dict[str, Any]) -> dict[str, str]:
        return {str(key): "" if value is None else str(value) for key, value in data.items()}

    @staticmethod
    def _response_payload(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
            return payload if isinstance(payload, dict) else {"response": payload}
        except ValueError:
            return {"response": response.text}
