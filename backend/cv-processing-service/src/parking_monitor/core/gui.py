import cv2
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from PIL import Image, ImageTk
import os
import sys
import threading

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

try:
    from scene3d import Scene3D, ParkingContainer3D
    from garage_3d import MultiContainerVisualizer
    from ray_proj_new_seg import process_video, DirectionTracker
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Убедитесь, что файлы scene3d.py, garage_3d.py и ray_proj_new_seg.py находятся в той же папке")
    raise


class ParkingContainerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("3D Гараж + YOLO Сегментация")
        self.root.geometry("1600x900")

        # Параметры по умолчанию
        self.length = 5.0
        self.width = 2.5
        self.height = 2.0
        self.center_height = 0.5

        # Создаём сцену
        self.scene = Scene3D()
        self.scene.center_height = self.center_height

        # Визуализатор
        self.opengl_visualizer = None

        # Для изображения
        self.current_image = None
        self.original_image = None
        self.photo = None
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.canvas_width = 0
        self.canvas_height = 0

        # Состояние рисования
        self.dragging_point = None
        self.dragging_container_id = None
        self.point_radius = 2

        # Точки контейнеров (для GUI)
        self.container_points = {}  # container_id -> list of points
        self.active_container_id = None

        # Режим редактирования
        self.editing_mode = False  # True когда точки можно двигать
        self.editing_container_id = None  # ID контейнера в режиме редактирования
        self.editing_points = []  # копия точек для редактирования

        # # Рисование линий
        # self.drawing_line = False
        # self.current_line_points = []
        # self.current_line_container_id = None

        # Переменные для видео
        self.video_path = None
        self.processing_thread = None

        self.setup_ui()

    def setup_ui(self):
        """Создание интерфейса"""
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Левая панель с прокруткой
        left_frame = ttk.Frame(main_frame, width=400)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_frame.pack_propagate(False)

        canvas = tk.Canvas(left_frame, bg='#f0f0f0', highlightthickness=0)
        scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=canvas.yview)
        self.content_frame = ttk.Frame(canvas)

        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.content_frame, anchor="nw", width=380)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_mouse_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", on_mouse_wheel)

        # Правая панель - изображение
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(right_frame, bg="gray", cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.canvas_click)
        # self.canvas.bind("<Button-3>", self.canvas_right_click)
        self.canvas.bind("<B1-Motion>", self.canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.canvas_release)

        self.create_controls()

    def create_controls(self):
        """Создание элементов управления"""
        ttk.Label(self.content_frame, text="3D Гараж + YOLO",
                  font=('Arial', 14, 'bold')).pack(pady=(10, 5), padx=5)

        ttk.Separator(self.content_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

        ttk.Button(self.content_frame, text="📹 Загрузить видео",
                   command=self.load_video).pack(pady=5, padx=5, fill=tk.X)

        ttk.Button(self.content_frame, text="🖼️ Загрузить изображение",
                   command=self.load_image).pack(pady=5, padx=5, fill=tk.X)

        ttk.Separator(self.content_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

        # Параметры гаража
        params_frame = ttk.LabelFrame(self.content_frame, text="Параметры гаража", padding=10)
        params_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Label(params_frame, text="Длина (м):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.length_var = tk.DoubleVar(value=self.length)
        ttk.Entry(params_frame, textvariable=self.length_var).grid(row=0, column=1, pady=2, padx=(0, 5))

        ttk.Label(params_frame, text="Ширина (м):").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.width_var = tk.DoubleVar(value=self.width)
        ttk.Entry(params_frame, textvariable=self.width_var).grid(row=1, column=1, pady=2, padx=(0, 5))

        ttk.Label(params_frame, text="Высота (м):").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.height_var = tk.DoubleVar(value=self.height)
        ttk.Entry(params_frame, textvariable=self.height_var).grid(row=2, column=1, pady=2, padx=(0, 5))

        ttk.Separator(self.content_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

        # Параметры проекции
        proj_frame = ttk.LabelFrame(self.content_frame, text="Параметры проекции", padding=10)
        proj_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Label(proj_frame, text="Высота центра (м):").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.center_height_var = tk.DoubleVar(value=self.center_height)
        self.center_height_var.trace('w', lambda *args: self.update_center_height())
        ttk.Entry(proj_frame, textvariable=self.center_height_var, width=10).grid(row=0, column=1, pady=2, padx=(0, 5))

        ttk.Separator(self.content_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

        # Управление контейнерами
        container_frame = ttk.LabelFrame(self.content_frame, text="Управление контейнерами", padding=10)
        container_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(container_frame, text="➕ Добавить базовый контейнер",
                   command=self.add_base_container).pack(pady=2, fill=tk.X)

        ttk.Button(container_frame, text="➕ Добавить новый контейнер",
                   command=self.add_container).pack(pady=2, fill=tk.X)

        ttk.Button(container_frame, text="✏️ Редактировать выбранный",
                   command=self.start_editing_container).pack(pady=2, fill=tk.X)

        ttk.Button(container_frame, text="  Выбрать активный контейнер",
                   command=self.select_active_container).pack(pady=2, fill=tk.X)

        list_frame = ttk.Frame(container_frame)
        list_frame.pack(pady=5, fill=tk.X)

        self.container_listbox = tk.Listbox(list_frame, height=4, selectbackground='#0078d7',
                                            selectforeground='white')
        self.container_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        list_scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.container_listbox.yview)
        list_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.container_listbox.config(yscrollcommand=list_scrollbar.set)

        self.container_listbox.bind('<<ListboxSelect>>', self.on_container_select)

        ttk.Button(container_frame, text="  Удалить выбранный контейнер",
                   command=self.delete_selected_container).pack(pady=2, fill=tk.X)

        self.container_status_var = tk.StringVar(value="Контейнеров: 0")
        ttk.Label(container_frame, textvariable=self.container_status_var,
                  foreground="green", font=('Arial', 9, 'bold')).pack(pady=5)

        ttk.Separator(self.content_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

        # Основные действия
        controls_frame = ttk.LabelFrame(self.content_frame, text="Основные действия", padding=10)
        controls_frame.pack(fill=tk.X, pady=5, padx=5)

        ttk.Button(controls_frame, text="  Создать/Обновить контейнер",
                   command=self.create_or_update_container).pack(pady=2, fill=tk.X)

        ttk.Button(controls_frame, text="  Отменить редактирование",
                   command=self.cancel_editing).pack(pady=2, fill=tk.X)

        # ttk.Button(controls_frame, text="  Начать рисовать линию",
        #            command=self.start_drawing_line).pack(pady=2, fill=tk.X)
        #
        # ttk.Button(controls_frame, text="  Завершить линию",
        #            command=self.finish_drawing_line).pack(pady=2, fill=tk.X)

        self.process_video_btn = ttk.Button(controls_frame, text="  Обработать видео YOLO",
                                            command=self.process_video_thread,
                                            state=tk.DISABLED)
        self.process_video_btn.pack(pady=2, fill=tk.X)

        self.process_video_fast_btn = ttk.Button(controls_frame, text="  Быстрая обработка (100 кадров)",
                                                 command=self.process_video_fast_thread,
                                                 state=tk.DISABLED)
        self.process_video_fast_btn.pack(pady=2, fill=tk.X)

        ttk.Button(controls_frame, text="  OpenGL 3D Визуализация",
                   command=self.show_3d_visualization).pack(pady=2, fill=tk.X)

        ttk.Separator(self.content_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

        # Очистка
        clear_frame = ttk.LabelFrame(self.content_frame, text="Очистка", padding=10)
        clear_frame.pack(fill=tk.X, pady=5, padx=5)

        # ttk.Button(clear_frame, text="  Очистить линии активного контейнера",
        #            command=self.clear_active_lines).pack(pady=2, fill=tk.X)

        ttk.Button(clear_frame, text="  Очистить точки активного контейнера",
                   command=self.clear_active_points).pack(pady=2, fill=tk.X)

        ttk.Button(clear_frame, text="  Очистить всё",
                   command=self.clear_all).pack(pady=2, fill=tk.X)

        ttk.Separator(self.content_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

        ttk.Button(self.content_frame, text="  Сохранить результат",
                   command=self.save_result).pack(pady=5, padx=5, fill=tk.X)

        ttk.Separator(self.content_frame, orient='horizontal').pack(fill='x', pady=5, padx=5)

        status_frame = ttk.LabelFrame(self.content_frame, text="Статус", padding=10)
        status_frame.pack(fill=tk.X, pady=(5, 10), padx=5)

        self.status_var = tk.StringVar(value="Готов к работе")
        status_label = ttk.Label(status_frame, textvariable=self.status_var,
                                 foreground="blue", wraplength=350, justify=tk.LEFT)
        status_label.pack()

    def update_center_height(self):
        """Обновляет высоту центра в сцене"""
        self.scene.center_height = self.center_height_var.get()

    # ==================== Загрузка файлов ====================

    def load_video(self):
        """Загрузка видео"""
        file_path = filedialog.askopenfilename(
            title="Выберите видеофайл",
            filetypes=[("Video files", "*.mp4 *.avi *.mov *.mkv *.MOV *.MP4")]
        )
        if file_path:
            try:
                cap = cv2.VideoCapture(file_path)
                if not cap.isOpened():
                    messagebox.showerror("Ошибка", "Не удалось открыть видеофайл")
                    return

                ret, first_frame = cap.read()
                if not ret:
                    messagebox.showerror("Ошибка", "Не удалось прочитать первый кадр")
                    cap.release()
                    return

                cap.release()

                self.video_path = file_path
                self.original_image = first_frame.copy()
                self.current_image = first_frame.copy()

                # Очищаем сцену
                self.scene = Scene3D()
                self.scene.center_height = self.center_height_var.get()
                self.scene.set_camera_from_image(first_frame.shape[:2])

                self.container_points = {}
                self.active_container_id = None
                self.editing_mode = False
                self.editing_container_id = None

                self.update_container_listbox()
                self.update_display()
                self.status_var.set(f"Видео загружено: {os.path.basename(file_path)}")

            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка загрузки видео: {str(e)}")

    def load_image(self):
        """Загрузка изображения"""
        file_path = filedialog.askopenfilename(
            title="Выберите изображение",
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff")]
        )
        if file_path:
            try:
                self.original_image = cv2.imread(file_path)
                if self.original_image is None:
                    messagebox.showerror("Ошибка", "Не удалось загрузить изображение")
                    return

                self.current_image = self.original_image.copy()
                self.video_path = None

                # Очищаем сцену
                self.scene = Scene3D()
                self.scene.center_height = self.center_height_var.get()
                self.container_points = {}
                self.active_container_id = None
                self.editing_mode = False
                self.editing_container_id = None

                self.update_container_listbox()
                self.update_display()
                self.status_var.set("Изображение загружено")

            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка загрузки: {str(e)}")

    # ==================== Управление контейнерами ====================

    def add_base_container(self):
        """Добавляет базовый контейнер"""
        if self.original_image is None:
            messagebox.showwarning("Предупреждение", "Сначала загрузите видео или изображение")
            return

        # Базовый контейнер всегда имеет ID 0
        self.container_points[0] = []
        self.active_container_id = 0
        self.start_editing_container()  # Сразу входим в режим редактирования
        self.update_container_listbox()
        self.status_var.set("Базовый контейнер: выберите 4 точки (можно двигать)")

    def add_container(self):
        """Добавляет новый контейнер"""
        if self.original_image is None:
            messagebox.showwarning("Предупреждение", "Сначала загрузите видео или изображение")
            return

        if self.scene.base_container_id is None:
            messagebox.showwarning("Предупреждение", "Сначала создайте базовый контейнер")
            return

        # Новый контейнер получает следующий ID
        new_id = max(list(self.container_points.keys()) + [-1]) + 1
        self.container_points[new_id] = []
        self.active_container_id = new_id
        self.start_editing_container()  # Сразу входим в режим редактирования
        self.update_container_listbox()
        self.status_var.set(f"Контейнер {new_id}: выберите 4 точки (можно двигать)")

    def start_editing_container(self):
        """Входит в режим редактирования выбранного контейнера"""
        if self.active_container_id is None:
            messagebox.showwarning("Предупреждение", "Сначала выберите контейнер")
            return

        # Если контейнер уже существует в сцене, берём его точки
        if self.active_container_id in self.scene.containers:
            container = self.scene.containers[self.active_container_id]
            self.editing_points = container.image_points.copy()
        else:
            # Иначе берём из временного хранилища
            self.editing_points = self.container_points.get(self.active_container_id, []).copy()

        self.editing_mode = True
        self.editing_container_id = self.active_container_id
        self.container_points[self.active_container_id] = self.editing_points
        self.status_var.set(f"Режим редактирования контейнера {self.active_container_id}. Двигайте точки")
        self.redraw_image_with_points()

    def cancel_editing(self):
        """Отменяет редактирование и возвращает сохранённые точки"""
        if not self.editing_mode:
            return

        if self.editing_container_id in self.scene.containers:
            # Возвращаем сохранённые в сцене точки
            container = self.scene.containers[self.editing_container_id]
            self.container_points[self.editing_container_id] = container.image_points.copy()
        elif self.editing_container_id in self.container_points:
            # Очищаем точки если контейнер ещё не создан
            self.container_points[self.editing_container_id] = []

        self.editing_mode = False
        self.editing_container_id = None
        self.editing_points = []
        self.status_var.set("Редактирование отменено")
        self.redraw_image_with_points()

    def select_active_container(self):
        """Выбор активного контейнера"""
        if not self.container_points:
            messagebox.showinfo("Информация", "Нет контейнеров")
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Выбор активного контейнера")
        dialog.geometry("300x300")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="Выберите контейнер:").pack(pady=10)

        listbox = tk.Listbox(dialog, height=10)
        listbox.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        for container_id in sorted(self.container_points.keys()):
            if container_id in self.scene.containers:
                listbox.insert(tk.END, f"Контейнер {container_id} [3D готов]")
            else:
                listbox.insert(tk.END, f"Контейнер {container_id} [требует 4 точки]")

        def on_select():
            selection = listbox.curselection()
            if selection:
                # Получаем ID из текста
                text = listbox.get(selection[0])
                container_id = int(text.split()[1])
                self.active_container_id = container_id

                # Если мы были в режиме редактирования, выходим из него
                if self.editing_mode:
                    self.cancel_editing()

                self.status_var.set(f"Активный контейнер: {container_id}")
                self.redraw_image_with_points()
                dialog.destroy()

        ttk.Button(dialog, text="Выбрать", command=on_select).pack(pady=10)

    def on_container_select(self, event):
        """Обработка выбора из списка"""
        selection = self.container_listbox.curselection()
        if selection:
            text = self.container_listbox.get(selection[0])
            container_id = int(text.split()[1])
            self.active_container_id = container_id

            # Если мы были в режиме редактирования, выходим из него
            if self.editing_mode:
                self.cancel_editing()

            self.status_var.set(f"Активный контейнер: {container_id}")
            self.redraw_image_with_points()

    def delete_selected_container(self):
        """Удаляет выбранный контейнер"""
        if self.active_container_id is None:
            messagebox.showwarning("Предупреждение", "Сначала выберите контейнер")
            return

        # Если мы в режиме редактирования этого контейнера, выходим
        if self.editing_mode and self.editing_container_id == self.active_container_id:
            self.editing_mode = False
            self.editing_container_id = None

        if self.active_container_id == 0:
            # Удаляем базовый контейнер - очищаем всё
            self.scene = Scene3D()
            self.scene.center_height = self.center_height_var.get()
            self.container_points = {}
            self.active_container_id = None
        else:
            # Удаляем обычный контейнер
            if self.active_container_id in self.container_points:
                del self.container_points[self.active_container_id]
            if self.active_container_id in self.scene.containers:
                del self.scene.containers[self.active_container_id]
            self.active_container_id = None

        self.update_container_listbox()
        self.redraw_image_with_points()
        self.status_var.set("Контейнер удален")

    def update_container_listbox(self):
        """Обновляет список контейнеров"""
        self.container_listbox.delete(0, tk.END)
        for container_id in sorted(self.container_points.keys()):
            if container_id in self.scene.containers:
                status = "[3D готов]"
                if self.editing_mode and self.editing_container_id == container_id:
                    status = "[РЕДАКТИРОВАНИЕ]"
                self.container_listbox.insert(tk.END, f"Контейнер {container_id} {status}")
            else:
                points_count = len(self.container_points.get(container_id, []))
                self.container_listbox.insert(tk.END, f"Контейнер {container_id} [{points_count}/4 точек]")
        self.container_status_var.set(f"Контейнеров: {len(self.container_points)}")

    # ==================== Работа с изображением ====================

    def update_display(self):
        """Обновляет отображение изображения"""
        if self.current_image is not None:
            image_rgb = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2RGB)
            image_pil = Image.fromarray(image_rgb)

            self.canvas_width = self.canvas.winfo_width()
            self.canvas_height = self.canvas.winfo_height()

            if self.canvas_width > 10 and self.canvas_height > 10:
                img_ratio = image_pil.width / image_pil.height
                canvas_ratio = self.canvas_width / self.canvas_height

                if img_ratio > canvas_ratio:
                    new_width = self.canvas_width
                    new_height = int(self.canvas_width / img_ratio)
                else:
                    new_height = self.canvas_height
                    new_width = int(self.canvas_height * img_ratio)

                self.scale_x = new_width / self.current_image.shape[1]
                self.scale_y = new_height / self.current_image.shape[0]

                image_pil = image_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)

            self.photo = ImageTk.PhotoImage(image_pil)
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor=tk.NW, image=self.photo)
            self.canvas.config(scrollregion=self.canvas.bbox(tk.ALL))

    def canvas_click(self, event):
        """Обработка клика на канвасе"""
        if self.original_image is None:
            return

        # # Режим рисования линии
        # if self.drawing_line:
        #     orig_x = event.x / self.scale_x
        #     orig_y = event.y / self.scale_y
        #     if (0 <= orig_x < self.original_image.shape[1] and
        #             0 <= orig_y < self.original_image.shape[0]):
        #         self.current_line_points.append([orig_x, orig_y])
        #         self.redraw_image_with_points()
        #         self.status_var.set(f"Точка линии добавлена. Всего: {len(self.current_line_points)}")
        #     return

        # Если не выбран контейнер
        if self.active_container_id is None:
            self.status_var.set("Сначала выберите или создайте контейнер")
            return

        # Получаем точки для активного контейнера
        points = self.container_points.get(self.active_container_id, [])

        # В режиме редактирования можно двигать существующие точки
        if self.editing_mode and len(points) == 4:
            for i, point in enumerate(points):
                canvas_x = point[0] * self.scale_x
                canvas_y = point[1] * self.scale_y
                if (abs(event.x - canvas_x) < 10 and abs(event.y - canvas_y) < 10):
                    self.dragging_point = i
                    self.dragging_container_id = self.active_container_id
                    return

        # Добавление новых точек (только если не в режиме редактирования или точек меньше 4)
        if not self.editing_mode or len(points) < 4:
            if len(points) < 4:
                orig_x = event.x / self.scale_x
                orig_y = event.y / self.scale_y
                if (0 <= orig_x < self.original_image.shape[1] and
                        0 <= orig_y < self.original_image.shape[0]):
                    points.append([orig_x, orig_y])
                    self.container_points[self.active_container_id] = points
                    self.redraw_image_with_points()
                    self.status_var.set(f"Контейнер {self.active_container_id}: точка {len(points)}/4")

                    # Если набрали 4 точки и не в режиме редактирования, автоматически входим в режим редактирования
                    if len(points) == 4 and not self.editing_mode:
                        self.start_editing_container()

    # def canvas_right_click(self, event):
    #     """Правый клик для тестирования проекции"""
    #     if self.original_image is None or self.active_container_id is None:
    #         return
    #     if self.active_container_id not in self.scene.containers:
    #         self.status_var.set("Сначала создайте 3D контейнер")
    #         return
    #
    #     container = self.scene.containers[self.active_container_id]
    #     orig_x = event.x / self.scale_x
    #     orig_y = event.y / self.scale_y
    #
    #     if (0 <= orig_x < self.original_image.shape[1] and
    #             0 <= orig_y < self.original_image.shape[0]):
    #         try:
    #             world_point = self.scene.image_to_world_point((orig_x, orig_y), container)
    #             world_point_height = self.scene.image_to_3d_at_height(
    #                 (orig_x, orig_y), container, self.center_height_var.get()
    #             )
    #
    #             self.scene.add_debug_point(world_point, self.active_container_id)
    #             if world_point_height is not None:
    #                 self.scene.add_debug_point(world_point_height, self.active_container_id)
    #
    #             self.redraw_image_with_points()
    #             self.status_var.set(
    #                 f"3D точка: ({world_point[0]:.1f}, {world_point[1]:.1f}, {world_point[2]:.1f})"
    #             )
    #         except Exception as e:
    #             self.status_var.set(f"Ошибка: {str(e)}")

    def canvas_drag(self, event):
        """Перетаскивание точки"""
        if self.dragging_point is not None and self.dragging_container_id is not None:
            orig_x = event.x / self.scale_x
            orig_y = event.y / self.scale_y
            orig_x = max(0, min(orig_x, self.original_image.shape[1] - 1))
            orig_y = max(0, min(orig_y, self.original_image.shape[0] - 1))

            points = self.container_points.get(self.dragging_container_id, [])
            if self.dragging_point < len(points):
                points[self.dragging_point] = [orig_x, orig_y]
                self.container_points[self.dragging_container_id] = points

                # Если мы в режиме редактирования, обновляем отображение в реальном времени
                if self.editing_mode and self.dragging_container_id == self.editing_container_id:
                    self.redraw_image_with_points()

    def canvas_release(self, event):
        """Отпускание точки"""
        if self.dragging_point is not None and self.dragging_container_id is not None:
            # Если мы в режиме редактирования и отпустили точку, обновляем предпросмотр
            if self.editing_mode and self.dragging_container_id == self.editing_container_id:
                self.show_container_preview()

        self.dragging_point = None
        self.dragging_container_id = None

    def show_container_preview(self):
        """Показывает предпросмотр контейнера в 3D (без сохранения в сцену)"""
        if not self.editing_mode or self.editing_container_id is None:
            return

        points = self.container_points.get(self.editing_container_id, [])
        if len(points) != 4:
            return

        # Визуально обновляем, но не сохраняем в сцену
        self.redraw_image_with_points()
        self.status_var.set(f"Предпросмотр контейнера {self.editing_container_id} (двигайте точки)")

    def redraw_image_with_points(self):
        """Перерисовывает изображение с точками и контейнерами"""
        if self.original_image is not None:
            self.current_image = self.original_image.copy()

            # Рисуем контейнеры из сцены (только зафиксированные)
            for container_id, container in self.scene.containers.items():
                self.draw_container_on_image(container, container_id, alpha=1.0)

            # Если в режиме редактирования, рисуем предпросмотр редактируемого контейнера
            if self.editing_mode and self.editing_container_id is not None:
                points = self.container_points.get(self.editing_container_id, [])
                if len(points) == 4:
                    # Рисуем полупрозрачный предпросмотр
                    self.draw_container_preview(self.editing_container_id, points, alpha=0.5)

            # Рисуем точки контейнеров
            for container_id, points in self.container_points.items():
                # Пропускаем, если это зафиксированный контейнер - его точки уже нарисованы через draw_container_on_image
                if container_id in self.scene.containers and not (
                        self.editing_mode and container_id == self.editing_container_id):
                    continue

                for point_idx, point in enumerate(points):
                    x, y = int(point[0]), int(point[1])

                    # Цвет зависит от режима
                    if self.editing_mode and container_id == self.editing_container_id:
                        colors = [(0, 255, 0), (255, 255, 0), (0, 255, 255), (255, 0, 255)]
                        color = colors[point_idx % len(colors)]
                        radius = 12
                    else:
                        colors = [(0, 0, 255), (255, 0, 0), (0, 255, 255), (255, 255, 0)]
                        color_idx = container_id % len(colors)
                        color = colors[color_idx]
                        radius = 8

                    cv2.circle(self.current_image, (x, y), radius, color, -1)

                    # Номер точки
                    if container_id == self.active_container_id:
                        cv2.putText(self.current_image, f"{point_idx + 1}", (x + 15, y - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

            # Рисуем отладочные точки (здесь нужна проекция из 3D в 2D, но это отдельно)
            # self.draw_debug_points_2d()

            self.update_display()

    def draw_container_preview(self, container_id, image_points, alpha=0.5):
        """Рисует предпросмотр контейнера (полупрозрачный)"""
        if len(image_points) != 4:
            return

        # Создаём оверлей
        overlay = self.current_image.copy()

        # Цвет в зависимости от ID
        colors = [(0, 255, 0), (0, 255, 255), (255, 165, 0), (255, 0, 255)]
        color_idx = container_id % len(colors)
        color = colors[color_idx]

        # Рисуем polygon
        points = np.array(image_points, dtype=np.int32)
        cv2.polylines(overlay, [points], True, color, 3)

        # Полупрозрачная заливка
        overlay_copy = overlay.copy()
        cv2.fillPoly(overlay_copy, [points], color)
        cv2.addWeighted(overlay_copy, alpha, overlay, 1 - alpha, 0, overlay)

        # Смешиваем с оригиналом
        cv2.addWeighted(overlay, alpha, self.current_image, 1 - alpha, 0, self.current_image)

        # Номер контейнера и размеры
        center = np.mean(image_points, axis=0).astype(int)
        cv2.putText(
            self.current_image,
            f"P{container_id} (preview)",
            (center[0] - 30, center[1]),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2
        )

        # Показываем размеры из GUI
        cv2.putText(
            self.current_image,
            f"{self.length_var.get():.1f}x{self.width_var.get():.1f}x{self.height_var.get():.1f}",
            (center[0] - 30, center[1] + 25),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
        )

    def world_to_image_point(self, world_point, container): 
        """Упрощённая обратная проекция из 3D в 2D"""
        if abs(world_point[1]) < 0.01:  # точка на полу
            point_ground = np.array([world_point[0], world_point[2], 1.0])
            img_point = container.homography @ point_ground
            img_point /= img_point[2]
            return [int(img_point[0]), int(img_point[1])]
        return None

    def draw_container_on_image(self, container, container_id, alpha=1.0):
        """Рисует зафиксированный контейнер на изображении используя сохраненные image_points"""
        if not hasattr(container, 'image_points') or container.image_points is None:
            return

        img_points = container.image_points.astype(np.int32)

        if len(img_points) == 4:
            colors = [(0, 255, 0), (0, 255, 255), (255, 165, 0), (255, 0, 255)]
            color_idx = container_id % len(colors)
            color = colors[color_idx]

            # Рисуем полигон
            if alpha < 1.0:
                overlay = self.current_image.copy()
                cv2.polylines(overlay, [img_points], True, color, 3)
                cv2.addWeighted(overlay, alpha, self.current_image, 1 - alpha, 0, self.current_image)
            else:
                cv2.polylines(self.current_image, [img_points], True, color, 3)

            # Добавляем текст с размерами
            center = np.mean(img_points, axis=0).astype(int)
            cv2.putText(
                self.current_image,
                f"P{container_id} ({container.length:.1f}x{container.width:.1f}x{container.height:.1f})",
                (center[0] - 50, center[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2
            )

    # ==================== Создание и обновление контейнеров ====================

    def create_or_update_container(self):
        """Фиксирует контейнер в сцене (выходит из режима редактирования)"""
        if self.original_image is None:
            messagebox.showwarning("Предупреждение", "Сначала загрузите видео или изображение")
            return

        if not self.editing_mode or self.editing_container_id is None:
            messagebox.showwarning("Предупреждение", "Сначала войдите в режим редактирования")
            return

        points = self.container_points.get(self.editing_container_id, [])
        if len(points) != 4:
            messagebox.showwarning("Предупреждение", "Нужно выбрать 4 точки")
            return

        # Получаем размеры из GUI
        length = self.length_var.get()
        width = self.width_var.get()
        height = self.height_var.get()

        try:
            if self.editing_container_id == 0:
                # Создаём/обновляем базовый контейнер
                if self.editing_container_id in self.scene.containers:
                    # Обновляем существующий
                    self.scene.update_container(
                        container_id=self.editing_container_id,
                        image_points=np.array(points),
                        length=length,
                        width=width,
                        height=height
                    )
                else:
                    # Создаём новый
                    self.scene.create_base_container(
                        image_points=np.array(points),
                        length=length,
                        width=width,
                        height=height
                    )
                self.status_var.set(f"Базовый контейнер зафиксирован!")
            else:
                # Создаём/обновляем обычный контейнер
                if self.editing_container_id in self.scene.containers:
                    # Обновляем существующий
                    self.scene.update_container(
                        container_id=self.editing_container_id,
                        image_points=np.array(points),
                        length=length,
                        width=width,
                        height=height
                    )
                else:
                    # Создаём новый
                    self.scene.create_container(
                        image_points=np.array(points),
                        length=length,
                        width=width,
                        height=height
                    )
                self.status_var.set(f"Контейнер {self.editing_container_id} зафиксирован!")

            # Выходим из режима редактирования
            self.editing_mode = False
            self.editing_container_id = None

            self.redraw_image_with_points()
            self.update_container_listbox()

            # Активируем кнопки обработки видео
            if self.scene.base_container_id is not None and self.video_path:
                self.process_video_btn.config(state=tk.NORMAL)
                self.process_video_fast_btn.config(state=tk.NORMAL)

        except Exception as e:
            error_msg = f"Ошибка создания контейнера: {str(e)}"
            self.status_var.set(error_msg)
            messagebox.showerror("Ошибка", error_msg)

    # ==================== Работа с линиями ====================

    # def start_drawing_line(self):
    #     """Начинает рисование линии"""
    #     if self.original_image is None:
    #         messagebox.showwarning("Предупреждение", "Сначала загрузите видео или изображение")
    #         return
    #     if self.active_container_id is None:
    #         messagebox.showwarning("Предупреждение", "Сначала выберите активный контейнер")
    #         return
    #     if self.active_container_id not in self.scene.containers:
    #         messagebox.showwarning("Предупреждение", "Сначала создайте 3D контейнер")
    #         return
    #
    #     # Если мы в режиме редактирования, выходим из него
    #     if self.editing_mode:
    #         self.cancel_editing()
    #
    #     self.drawing_line = True
    #     self.current_line_points = []
    #     self.current_line_container_id = self.active_container_id
    #     self.status_var.set("Режим рисования линии: кликайте по изображению")
    #     self.canvas.config(cursor="pencil")

    # def finish_drawing_line(self):
    #     """Завершает рисование линии"""
    #     if not self.drawing_line:
    #         return
    #     if len(self.current_line_points) >= 2:
    #         try:
    #             container = self.scene.containers[self.current_line_container_id]
    #             # Проецируем точки линии в 3D
    #             world_points = []
    #             for img_point in self.current_line_points:
    #                 world_point = self.scene.image_to_world_point(img_point, container)
    #                 world_points.append(world_point)
    #
    #             world_points = np.array(world_points)
    #             self.scene.add_floor_line(self.current_line_container_id, world_points)
    #             self.status_var.set(f"Линия добавлена в контейнер {self.current_line_container_id}")
    #         except Exception as e:
    #             self.status_var.set(f"Ошибка создания линии: {str(e)}")
    #
    #     self.drawing_line = False
    #     self.current_line_points = []
    #     self.current_line_container_id = None
    #     self.canvas.config(cursor="crosshair")
    #     self.redraw_image_with_points()
    #
    # def clear_active_lines(self):
    #     """Очищает линии активного контейнера"""
    #     if self.active_container_id is not None:
    #         if self.active_container_id in self.scene.floor_lines:
    #             self.scene.floor_lines[self.active_container_id] = []
    #         self.current_line_points = []
    #         self.drawing_line = False
    #         self.redraw_image_with_points()
    #         self.status_var.set(f"Линии контейнера {self.active_container_id} очищены")
    #         self.canvas.config(cursor="crosshair")

    def clear_active_points(self):
        """Очищает точки активного контейнера"""
        if self.active_container_id is not None:
            if self.active_container_id in self.container_points:
                self.container_points[self.active_container_id] = []
            if self.active_container_id in self.scene.containers:
                del self.scene.containers[self.active_container_id]

            # Если мы в режиме редактирования этого контейнера, выходим
            if self.editing_mode and self.editing_container_id == self.active_container_id:
                self.editing_mode = False
                self.editing_container_id = None

            self.redraw_image_with_points()
            self.update_container_listbox()
            self.status_var.set(f"Точки контейнера {self.active_container_id} очищены")

    def clear_all(self):
        """Очищает всё"""
        self.scene = Scene3D()
        self.scene.center_height = self.center_height_var.get()
        self.container_points = {}
        self.active_container_id = None
        self.editing_mode = False
        self.editing_container_id = None
        # self.current_line_points = []
        # self.drawing_line = False
        self.redraw_image_with_points()
        self.update_container_listbox()
        self.status_var.set("Всё очищено")
        self.process_video_btn.config(state=tk.DISABLED)
        self.process_video_fast_btn.config(state=tk.DISABLED)

    # ==================== Визуализация ====================

    def show_3d_visualization(self):
        """Показывает 3D визуализацию"""
        if not self.scene.containers:
            messagebox.showwarning("Предупреждение", "Сначала создайте хотя бы один 3D контейнер")
            return

        # Если мы в режиме редактирования, выходим из него
        if self.editing_mode:
            self.cancel_editing()

        try:
            self.opengl_visualizer = MultiContainerVisualizer(self.scene)
            self.opengl_visualizer.run_visualization()
        except Exception as e:
            messagebox.showerror("Ошибка", f"Ошибка 3D визуализации: {str(e)}")

    def save_result(self):
        """Сохраняет текущее изображение"""
        if self.current_image is None:
            messagebox.showwarning("Предупреждение", "Нет изображения для сохранения")
            return
        file_path = filedialog.asksaveasfilename(
            title="Сохранить результат",
            defaultextension=".jpg",
            filetypes=[("JPEG files", "*.jpg"), ("PNG files", "*.png")]
        )
        if file_path:
            try:
                cv2.imwrite(file_path, self.current_image)
                messagebox.showinfo("Успех", f"Изображение сохранено: {file_path}")
            except Exception as e:
                messagebox.showerror("Ошибка", f"Ошибка сохранения: {str(e)}")

    # ==================== Обработка видео ====================

    def process_video_thread(self):
        """Запускает обработку видео в отдельном потоке"""
        if not self.video_path:
            messagebox.showwarning("Предупреждение", "Сначала загрузите видео")
            return
        if not self.scene.base_container_id:
            messagebox.showwarning("Предупреждение", "Сначала создайте базовый контейнер")
            return

        # Если мы в режиме редактирования, выходим из него
        if self.editing_mode:
            self.cancel_editing()

        self.process_video_btn.config(state=tk.DISABLED, text="Обработка...")
        self.process_video_fast_btn.config(state=tk.DISABLED)
        self.status_var.set("Обработка видео... ждите")

        self.processing_thread = threading.Thread(target=self._process_video, daemon=True)
        self.processing_thread.start()

    def _process_video(self):
        """Выполняется в потоке"""
        try:
            def progress_callback(percent):
                self.root.after(0, lambda: self.status_var.set(f"Обработка видео: {percent}%"))

            processed_count = process_video(
                video_path=self.video_path,
                scene=self.scene,
                model_path="yolo11n-seg.pt",
                callback=progress_callback
            )

            self.root.after(0, lambda: self._on_video_processed(processed_count))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка обработки видео", str(e)))
            self.root.after(0, lambda: self._reset_video_buttons())

    def process_video_fast_thread(self):
        """Быстрая обработка видео"""
        if not self.video_path:
            messagebox.showwarning("Предупреждение", "Сначала загрузите видео")
            return
        if not self.scene.base_container_id:
            messagebox.showwarning("Предупреждение", "Сначала создайте базовый контейнер")
            return

        # Если мы в режиме редактирования, выходим из него
        if self.editing_mode:
            self.cancel_editing()

        self.process_video_btn.config(state=tk.DISABLED)
        self.process_video_fast_btn.config(state=tk.DISABLED, text="Быстрая обработка...")
        self.status_var.set("Быстрая обработка видео...")

        self.processing_thread = threading.Thread(target=self._process_video_fast, daemon=True)
        self.processing_thread.start()

    def _process_video_fast(self):
        """Быстрая обработка в потоке"""
        try:
            def progress_callback(percent):
                self.root.after(0, lambda: self.status_var.set(f"Быстрая обработка: {percent}%"))

            frames_data, debug_images = process_video(
                video_path=self.video_path,
                scene=self.scene,
                model_path="yolo11n-seg.pt",
                max_frames=100,
                callback=progress_callback
            )

            self.root.after(0, lambda: self._on_video_processed(len(frames_data)))

        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Ошибка быстрой обработки", str(e)))
            self.root.after(0, lambda: self._reset_video_buttons())

    def _on_video_processed(self, processed_count):
        self._reset_video_buttons()
        status = f"Видео обработано, кадров: {processed_count}."
        self.status_var.set(status)
        messagebox.showinfo("Готово", f"Обработка завершена.\n{status}")

    def _reset_video_buttons(self):
        """Сбрасывает состояние кнопок видео"""
        self.process_video_btn.config(state=tk.NORMAL, text="  Обработать видео YOLO")
        self.process_video_fast_btn.config(state=tk.NORMAL, text="  Быстрая обработка (100 кадров)")

    def on_resize(self, event):
        """Обработка изменения размера окна"""
        if event.widget == self.canvas:
            self.update_display()


def main():
    root = tk.Tk()
    app = ParkingContainerApp(root)
    root.bind("<Configure>", app.on_resize)
    root.mainloop()


if __name__ == "__main__":
    main()