import asyncio
import subprocess
import cv2
import numpy as np
import websockets
from collections import deque

DEV = "eba508c57aec4d80bca445d53f5d7b4b"
WS_URL = f"wss://sr-171-25-235-76.ipeye.ru/ws/mp4/live?name={DEV}&mode=online"
WIDTH, HEIGHT = 1280, 720
FFMPEG_PATH = r"C:\Users\Den4ik\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe"


class AsyncVideoStream:
    def __init__(self):
        self.frame_queue = deque(maxlen=2)  # только 2 кадра для свежести
        self.latest_frame = None

    async def stream(self):
        headers = {
            "Origin": "https://ipeye.ru",
            "User-Agent": "Mozilla/5.0"
        }

        ffmpeg = subprocess.Popen(
            [
                FFMPEG_PATH,
                "-loglevel", "quiet",
                "-f", "mp4",
                "-i", "pipe:0",
                "-f", "rawvideo",
                "-pix_fmt", "bgr24",
                "-vf", f"scale={WIDTH}:{HEIGHT}",
                "pipe:1"
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        )

        frame_size = WIDTH * HEIGHT * 3

        async with websockets.connect(WS_URL, additional_headers=headers) as ws:
            print("✅ WebSocket подключён")
            await ws.recv()

            loop = asyncio.get_event_loop()

            try:
                while True:
                    # Асинхронное чтение данных
                    data = await ws.recv()
                    if isinstance(data, bytes):
                        # Асинхронная запись в ffmpeg
                        await loop.run_in_executor(None, ffmpeg.stdin.write, data)
                        await loop.run_in_executor(None, ffmpeg.stdin.flush)

                        # Асинхронное чтение кадра
                        raw = await loop.run_in_executor(None, ffmpeg.stdout.read, frame_size)
                        if raw and len(raw) == frame_size:
                            frame = np.frombuffer(raw, dtype=np.uint8).reshape((HEIGHT, WIDTH, 3))
                            self.latest_frame = frame

            except Exception as e:
                print(f"Ошибка: {e}")
            finally:
                ffmpeg.stdin.close()
                ffmpeg.terminate()

    async def display_loop(self):
        cv2.namedWindow("Camera", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("Camera", WIDTH, HEIGHT)

        while True:
            if self.latest_frame is not None:
                cv2.imshow("Camera", self.latest_frame)

            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break

            await asyncio.sleep(0.033)  # ~30 FPS

        cv2.destroyAllWindows()


async def main():
    streamer = AsyncVideoStream()
    # Запускаем оба процесса конкурентно
    await asyncio.gather(
        streamer.stream(),
        streamer.display_loop()
    )


if __name__ == "__main__":
    asyncio.run(main())