"""
Headless stream ingestion helpers.
"""

import asyncio
from typing import Final

import cv2
import httpx
import numpy as np

from src.clients.cv_client import CVServiceClient


FRAME_PULL_TIMEOUT_SECONDS: Final[float] = 10.0
FRAME_PUSH_INTERVAL_SECONDS: Final[float] = 0.25
RETRY_DELAY_SECONDS: Final[float] = 2.0


def _build_snapshot_url(server_ip: str, dev: str) -> str:
    return f"http://{server_ip}/{dev}/img.jpeg"


async def _fetch_snapshot_bytes(
    client: httpx.AsyncClient,
    server_ip: str,
    dev: str,
) -> bytes:
    response = await client.get(_build_snapshot_url(server_ip, dev))
    response.raise_for_status()
    return response.content


def _normalize_frame(raw_bytes: bytes) -> bytes | None:
    frame_array = np.frombuffer(raw_bytes, dtype=np.uint8)
    frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
    if frame is None:
        return None

    ok, encoded = cv2.imencode(".jpg", frame)
    if not ok:
        return None
    return encoded.tobytes()


async def run_stream(
    cv_job_id: str,
    dev: str,
    server_ip: str,
    cv_client: CVServiceClient,
    stop_event: asyncio.Event,
) -> None:
    """
    Pulls JPEG snapshots from the camera endpoint and forwards frames to CV service.
    Designed to fail softly: temporary network/camera problems should not crash the API.
    """
    timeout = httpx.Timeout(FRAME_PULL_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout) as snapshot_client:
        while not stop_event.is_set():
            try:
                snapshot_bytes = await _fetch_snapshot_bytes(snapshot_client, server_ip, dev)
                frame_bytes = _normalize_frame(snapshot_bytes)
                if frame_bytes is not None:
                    await cv_client.push_frame(cv_job_id, frame_bytes)
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=FRAME_PUSH_INTERVAL_SECONDS,
                )
            except asyncio.TimeoutError:
                continue
            except httpx.HTTPError:
                await asyncio.sleep(RETRY_DELAY_SECONDS)
            except Exception:
                await asyncio.sleep(RETRY_DELAY_SECONDS)
