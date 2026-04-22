import cv2
import time
import threading
import queue
import requests
import numpy as np
from datetime import datetime
from urllib.parse import urlparse
import json

# Данные камеры из API
CAMERA_DATA = {
    "devcode": "cd248268492540d5adf3fe86b3d1bd84",
    "name": "Камера 5003 вверх по схеме",
    "video_links": {
        "hls": "https://sr-171-25-235-75.ipeye.ru/api/v1/stream/cd248268492540d5adf3fe86b3d1bd84/hls/index.m3u8",
        "rtmp": "rtmp://sr-171-25-235-75.ipeye.ru/cd248268492540d5adf3fe86b3d1bd84",
        "rtsp": "rtsp://sr-171-25-235-75.ipeye.ru/cd248268492540d5adf3fe86b3d1bd84",
        "mse": "wss://sr-171-25-235-75.ipeye.ru/ws/mp4/live?name=cd248268492540d5adf3fe86b3d1bd84"
    }
}


class MJPEGStreamCapture:
    """Захват MJPEG потока через HTTP с постоянным соединением"""

    def __init__(self, base_url, devcode):
        self.base_url = base_url
        self.devcode = devcode
        self.frame_queue = queue.Queue(maxsize=30)
        self.is_running = False
        self.capture_thread = None
        self.session = None

    def start(self):
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        print("MJPEG захват запущен")

    def stop(self):
        self.is_running = False
        if self.session:
            self.session.close()

    def get_frame(self, timeout=0.033):
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _capture_loop(self):
        """Цикл захвата MJPEG потока"""
        # Используем API для получения live изображения
        live_url = f"https://api.ipeye.ru/device/jpeg/online/{self.devcode}/image.jpeg"

        while self.is_running:
            try:
                # Создаем сессию с keep-alive
                if not self.session:
                    self.session = requests.Session()
                    self.session.headers.update({
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                        'Connection': 'keep-alive'
                    })

                # Получаем изображение
                response = self.session.get(live_url, timeout=5)

                if response.status_code == 200:
                    # Конвертируем JPEG в кадр
                    img_array = np.frombuffer(response.content, np.uint8)
                    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

                    if frame is not None:
                        # Добавляем в очередь
                        try:
                            self.frame_queue.put_nowait(frame)
                        except queue.Full:
                            try:
                                self.frame_queue.get_nowait()
                                self.frame_queue.put_nowait(frame)
                            except:
                                pass

                # Небольшая задержка для контроля FPS
                time.sleep(0.05)  # ~20 FPS

            except requests.exceptions.RequestException as e:
                print(f"HTTP ошибка: {e}")
                time.sleep(1)
                # Пересоздаем сессию
                if self.session:
                    self.session.close()
                    self.session = None
            except Exception as e:
                print(f"Ошибка: {e}")
                time.sleep(1)


class WebSocketCapture:
    """Захват через WebSocket (MSE поток)"""

    def __init__(self, ws_url):
        self.ws_url = ws_url
        self.frame_queue = queue.Queue(maxsize=30)
        self.is_running = False
        self.capture_thread = None

    def start(self):
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        print("WebSocket захват запущен")

    def stop(self):
        self.is_running = False

    def get_frame(self, timeout=0.033):
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _capture_loop(self):
        """Цикл захвата через WebSocket"""
        try:
            # Пытаемся использовать websocket-client если установлен
            import websocket
            import base64

            def on_message(ws, message):
                # Обработка сообщения (здесь нужно парсить MP4 фрагменты)
                # Это сложно, поэтому лучше использовать другие методы
                pass

            ws = websocket.WebSocketApp(self.ws_url, on_message=on_message)
            ws.run_forever()

        except ImportError:
            print("websocket-client не установлен. Установите: pip install websocket-client")
            time.sleep(1)
        except Exception as e:
            print(f"WebSocket ошибка: {e}")
            time.sleep(1)


class HLSStreamCapture:
    """Захват HLS потока через OpenCV"""

    def __init__(self, hls_url):
        self.hls_url = hls_url
        self.frame_queue = queue.Queue(maxsize=30)
        self.is_running = False
        self.capture_thread = None
        self.cap = None

    def start(self):
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        print("HLS захват запущен")

    def stop(self):
        self.is_running = False
        if self.cap:
            self.cap.release()

    def get_frame(self, timeout=0.033):
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _capture_loop(self):
        """Цикл захвата HLS потока"""
        reconnect_delay = 1

        while self.is_running:
            try:
                # Создаем захват
                self.cap = cv2.VideoCapture(self.hls_url)

                if not self.cap.isOpened():
                    print("  ✗ Не удалось открыть HLS поток")
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 2, 30)
                    continue

                print("  ✓ HLS поток открыт")
                reconnect_delay = 1

                while self.is_running:
                    ret, frame = self.cap.read()

                    if not ret:
                        print("  ✗ Потеря кадра")
                        break

                    # Добавляем в очередь
                    try:
                        self.frame_queue.put_nowait(frame)
                    except queue.Full:
                        try:
                            self.frame_queue.get_nowait()
                            self.frame_queue.put_nowait(frame)
                        except:
                            pass

                if self.cap:
                    self.cap.release()
                    self.cap = None

            except Exception as e:
                print(f"Ошибка HLS: {e}")

            if not self.is_running:
                break

            print(f"Переподключение через {reconnect_delay}с...")
            time.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 30)


class DirectAPIStream:
    """Прямой захват через API IPEye (самый надежный)"""

    def __init__(self, devcode):
        self.devcode = devcode
        self.frame_queue = queue.Queue(maxsize=30)
        self.is_running = False
        self.capture_thread = None

    def start(self):
        self.is_running = True
        self.capture_thread = threading.Thread(target=self._capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        print("Direct API захват запущен")

    def stop(self):
        self.is_running = False

    def get_frame(self, timeout=0.033):
        try:
            return self.frame_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def _capture_loop(self):
        """Цикл захвата через прямой API запрос"""
        api_url = f"https://api.ipeye.ru/device/jpeg/online/{self.devcode}/image.jpeg"
        session = requests.Session()

        while self.is_running:
            try:
                # Получаем JPEG изображение
                response = session.get(api_url, timeout=5)

                if response.status_code == 200:
                    # Конвертируем в OpenCV формат
                    img_array = np.frombuffer(response.content, np.uint8)
                    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

                    if frame is not None:
                        # Добавляем информацию о времени
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        cv2.putText(frame, timestamp, (10, 30),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

                        # Добавляем в очередь
                        try:
                            self.frame_queue.put_nowait(frame)
                        except queue.Full:
                            try:
                                self.frame_queue.get_nowait()
                                self.frame_queue.put_nowait(frame)
                            except:
                                pass

                # Контроль FPS - примерно 10-15 кадров в секунду
                time.sleep(0.07)

            except Exception as e:
                print(f"API ошибка: {e}")
                time.sleep(2)

        session.close()


def main():
    """Основная функция"""
    print("=" * 60)
    print("IPEYE Camera Stream Player - Рабочая версия")
    print("=" * 60)

    devcode = CAMERA_DATA['devcode']
    print(f"Камера: {CAMERA_DATA['name']}")
    print(f"Devcode: {devcode}")

    print("\n" + "=" * 60)
    print("ВЫБОР МЕТОДА ПОДКЛЮЧЕНИЯ")
    print("=" * 60)
    print("1. Direct API (HTTP JPEG) - РЕКОМЕНДУЕТСЯ")
    print("2. HLS поток")
    print("3. MJPEG поток")
    print("4. WebSocket (экспериментально)")

    choice = input("\nВаш выбор (1-4): ").strip()

    if choice == '1':
        capture = DirectAPIStream(devcode)
    elif choice == '2':
        hls_url = CAMERA_DATA['video_links']['hls']
        capture = HLSStreamCapture(hls_url)
    elif choice == '3':
        capture = MJPEGStreamCapture(CAMERA_DATA['video_links']['hls'], devcode)
    elif choice == '4':
        ws_url = CAMERA_DATA['video_links']['mse']
        capture = WebSocketCapture(ws_url)
    else:
        print("Используем Direct API (рекомендуемый)")
        capture = DirectAPIStream(devcode)

    # Запускаем захват
    capture.start()

    # Создаем окно
    cv2.namedWindow("IPEye Camera", cv2.WINDOW_NORMAL)

    print("\nУправление:")
    print("  q, ESC - выход")
    print("  s - сохранить скриншот")
    print("  + / - - увеличить/уменьшить окно")
    print("  f - полноэкранный режим")
    print("=" * 60)

    frame_count = 0
    start_time = time.time()

    try:
        while True:
            frame = capture.get_frame(timeout=1)

            if frame is not None:
                frame_count += 1

                # Вычисляем FPS
                elapsed = time.time() - start_time
                if elapsed > 1.0:
                    fps = frame_count / elapsed
                    cv2.putText(frame, f"FPS: {fps:.1f}", (10, 60),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.putText(frame, f"Method: {capture.__class__.__name__}", (10, 90),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                    frame_count = 0
                    start_time = time.time()

                # Показываем кадр
                cv2.imshow("IPEye Camera", frame)

                key = cv2.waitKey(1) & 0xFF

                if key == ord('q') or key == 27:
                    print("\nВыход...")
                    break
                elif key == ord('s'):
                    filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                    cv2.imwrite(filename, frame)
                    print(f"Скриншот сохранен: {filename}")
                elif key == ord('+'):
                    current_size = cv2.getWindowImageRect("IPEye Camera")
                    cv2.resizeWindow("IPEye Camera", current_size[2] + 100, current_size[3] + 75)
                elif key == ord('-'):
                    current_size = cv2.getWindowImageRect("IPEye Camera")
                    cv2.resizeWindow("IPEye Camera", max(400, current_size[2] - 100), max(300, current_size[3] - 75))
                elif key == ord('f'):
                    cv2.setWindowProperty("IPEye Camera", cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

            else:
                # Показываем сообщение об ожидании
                blank = np.zeros((720, 1280, 3), dtype=np.uint8)
                cv2.putText(blank, f"Waiting for stream... (Queue: {capture.frame_queue.qsize()})",
                            (100, 360), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(blank, f"Method: {capture.__class__.__name__}",
                            (100, 400), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                cv2.putText(blank, "Press 1 to use Direct API (recommended)",
                            (100, 440), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.imshow("IPEye Camera", blank)

                key = cv2.waitKey(100) & 0xFF
                if key == ord('1'):
                    print("Переключение на Direct API...")
                    capture.stop()
                    capture = DirectAPIStream(devcode)
                    capture.start()

    except KeyboardInterrupt:
        print("\nПрерывание пользователем")
    finally:
        capture.stop()
        cv2.destroyAllWindows()
        print("Программа завершена")


if __name__ == "__main__":
    main()