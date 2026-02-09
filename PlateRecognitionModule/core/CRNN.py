import torch
import torch.nn as nn
from torchvision import transforms
import torch.ao.quantization.quantize_fx as quantize_fx
from torch.ao.quantization import QConfigMapping
import numpy as np


class CRNN(nn.Module):
    def __init__(self, num_classes):
        super(CRNN, self).__init__()

        # --- CNN часть (Глаза) ---
        self.cnn = nn.Sequential(
            nn.Conv2d(1, 64, kernel_size=3, padding=1),
            nn.ReLU(True),
            nn.MaxPool2d(2, 2),  # -> height: 16

            nn.Conv2d(64, 128, kernel_size=3, padding=1),
            nn.ReLU(True),
            nn.MaxPool2d(2, 2),  # -> height: 8

            nn.Conv2d(128, 256, kernel_size=3, padding=1),
            nn.BatchNorm2d(256),
            nn.ReLU(True),

            nn.Conv2d(256, 256, kernel_size=3, padding=1),
            nn.ReLU(True),
            nn.MaxPool2d((2, 1), (2, 1)),  # -> height: 4

            nn.Conv2d(256, 512, kernel_size=3, padding=1),
            nn.BatchNorm2d(512),
            nn.ReLU(True),

            nn.Conv2d(512, 512, kernel_size=3, padding=1),
            nn.ReLU(True),
            nn.MaxPool2d((2, 1), (2, 1))  # -> height: 2. ЭТОГО СЛОЯ НЕ БЫЛО, ДОБАВЛЯЕМ ЕГО!
        )

        # --- RNN часть (Мозг) ---

        self.rnn = nn.LSTM(512 * 2, 256, bidirectional=True, num_layers=2, batch_first=True)

        # --- Classifier (Рот) ---
        self.classifier = nn.Linear(512, num_classes)

    def forward(self, x):
        # Прогоняем через CNN
        x = self.cnn(x)  # -> (batch, 512, 2, 32)

        # "Распрямляем" выход CNN для подачи в RNN
        # объединяем каналы и высоту
        batch, channels, height, width = x.size()
        # Заменяем .view() на .reshape() для большей надежности
        x = x.reshape(batch, channels * height, width)

        # Меняем оси местами для RNN, который ожидает (batch, seq_len, features)
        x = x.permute(0, 2, 1)  # -> (batch, 32, 1024)

        # Прогоняем через RNN
        x, _ = self.rnn(x)  # -> (batch, 32, 512)

        # Прогоняем через классификатор
        x = self.classifier(x)  # -> (batch, 32, num_classes)

        # Для CTCLoss нам нужен формат (sequence_length, batch, num_classes)
        x = x.permute(1, 0, 2)  # -> (32, batch, num_classes)
        x = nn.functional.log_softmax(x, dim=2)

        return x


class CRNNRecognizer:
    """Обертка для квантованной модели распознавания CRNN."""

    OCR_IMG_HEIGHT: int = 32
    OCR_IMG_WIDTH: int = 128
    OCR_ALPHABET: str = '0123456789ABCEHKMOPTXY'

    def __init__(self, model_path: str, device: str):
        
        self.device = torch.device(device)
        self.transform = transforms.Compose([
            transforms.ToPILImage(), transforms.Grayscale(),
            transforms.Resize((CRNNRecognizer.OCR_IMG_HEIGHT, CRNNRecognizer.OCR_IMG_WIDTH)),
            transforms.ToTensor(), transforms.Normalize(mean=[0.5], std=[0.5])
        ])
        self.int_to_char = {i + 1: char for i, char in enumerate(CRNNRecognizer.OCR_ALPHABET)}
        self.int_to_char[0] = ''  # CTC Blank token

        num_classes = len(CRNNRecognizer.OCR_ALPHABET) + 1

        # 1. Создаем "пустой" скелет модели и переводим в режим инференса
        model_to_load = CRNN(num_classes).eval()

        # 2. Готовим его к квантизации точно так же, как при сохранении
        qconfig_mapping = QConfigMapping().set_global(torch.ao.quantization.get_default_qconfig('fbgemm'))
        example_inputs = (torch.randn(1, 1, CRNNRecognizer.OCR_IMG_HEIGHT, CRNNRecognizer.OCR_IMG_WIDTH),)
        model_prepared = quantize_fx.prepare_fx(model_to_load, qconfig_mapping, example_inputs)
        model_quantized = quantize_fx.convert_fx(model_prepared)

        # 3. И только теперь загружаем сохраненные веса
        model_quantized.load_state_dict(torch.load(model_path, map_location=device))
        self.model = model_quantized
        print("✅ Распознаватель OCR (INT8) успешно загружен.")

    @torch.no_grad()
    def recognize(self, plate_image: np.ndarray) -> str:
        preprocessed_plate = self.transform(plate_image).unsqueeze(0).to(self.device)
        preds = self.model(preprocessed_plate)
        return self._decode(preds)

    def _decode(self, preds: torch.Tensor) -> str:
        preds = preds.permute(1, 0, 2).argmax(dim=2)[0]  # Упрощаем и берем первый элемент батча
        decoded_seq = []
        last_char_idx = 0
        for char_idx in preds:
            char_idx = char_idx.item()
            if char_idx != 0 and char_idx != last_char_idx:
                decoded_seq.append(self.int_to_char.get(char_idx, ''))
            last_char_idx = char_idx
        return "".join(decoded_seq)
