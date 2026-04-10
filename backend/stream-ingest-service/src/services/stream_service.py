import requests
import time
import cv2
import numpy as np
from datetime import datetime


def simple_frame_capture():
    """Максимально простая функция захвата"""
    devcode = "cd248268492540d5adf3fe86b3d1bd84"

    # Прямой URL без API
    url = f"http://sr-171-25-235-75.ipeye.ru/{devcode}/img.jpeg"

    while True:
        try:
            # Простой GET запрос
            response = requests.get(url, timeout=5)

            if response.status_code == 200:
                # Конвертируем в изображение
                img_array = np.frombuffer(response.content, np.uint8)
                frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

                if frame is not None:
                    # Показываем
                    cv2.imshow("Camera", frame)

                    # Добавляем время
                    cv2.putText(frame, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

            # Ждем 0.1 секунды (~10 FPS)
            if cv2.waitKey(100) & 0xFF == ord('q'):
                break

        except Exception as e:
            print(f"Ошибка: {e}")
            time.sleep(2)

    cv2.destroyAllWindows()


if __name__ == "__main__":
    simple_frame_capture()