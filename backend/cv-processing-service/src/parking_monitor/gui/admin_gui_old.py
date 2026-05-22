# gui/admin_gui.py

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import cv2
import numpy as np
from PIL import Image, ImageTk
import threading
import os
from typing import List, Tuple, Optional, Dict, Any
import json

from parking_monitor.core.scene3d import Scene3D, ParkingContainer3D, CameraCalibration
from parking_monitor.db.repository import ParkingRepository



class AdminGUI:
    """
    Графический интерфейс администратора парковки.
    Работает с временной 3D сценой (Scene3D), изменения сохраняются в БД только по команде.
    """

    def __init__(self, root: tk.Tk, db_repo: ParkingRepository):
        self.root = root
        self.root.title("Parking Monitor - Admin Interface")
        self.root.geometry("1400x800")

        self.db = db_repo

        # Временная 3D сцена для текущей камеры
        self.temp_scene: Optional[Scene3D] = None
        self.current_camera_id: Optional[int] = None
        self.current_camera_info: Optional[Dict] = None

        # Изображение
        self.current_image: Optional[np.ndarray] = None
        self.original_image: Optional[np.ndarray] = None
        self.image_shape: Optional[Tuple[int, int]] = None

        # Режимы и состояние рисования
        self.mode = "view"  # view, draw_container, edit_container
        self.drawing_points: List[Tuple[float, float]] = []
        self.editing_container_id: Optional[int] = None
        self.dragging_point_idx: Optional[int] = None
        self.dragging_point = False

        # Масштабирование изображения
        self.scale_x = 1.0
        self.scale_y = 1.0
        self.image_offset_x = 0
        self.image_offset_y = 0
        self.canvas_photo = None

        # Флаг наличия несохраненных изменений
        self.has_unsaved_changes = False

        # Создаем интерфейс
        self._setup_ui()

        # Загружаем список камер
        self._load_cameras()

    def _setup_ui(self):
        """Создает интерфейс"""
        # Главное меню
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Файл", menu=file_menu)
        file_menu.add_command(label="Загрузить изображение", command=self._load_image)
        file_menu.add_command(label="Сохранить разметку в JSON", command=self._save_markup)
        file_menu.add_command(label="Загрузить разметку из JSON", command=self._load_markup)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.root.quit)

        view_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Вид", menu=view_menu)
        view_menu.add_command(label="3D визуализация", command=self._show_3d)
        view_menu.add_command(label="Обновить изображение", command=self._refresh_view)

        # Основной контейнер с разделителем
        main_paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Левая панель - управление (с прокруткой)
        left_container = ttk.Frame(main_paned, width=350)
        main_paned.add(left_container, weight=1)

        # Создаем Canvas для прокрутки
        left_canvas = tk.Canvas(left_container, highlightthickness=0)
        left_scrollbar = ttk.Scrollbar(left_container, orient="vertical", command=left_canvas.yview)
        left_canvas.configure(yscrollcommand=left_scrollbar.set)

        # Фрейм, который будет прокручиваться
        left_frame = ttk.Frame(left_canvas)
        left_frame.bind("<Configure>", lambda e: left_canvas.configure(scrollregion=left_canvas.bbox("all")))

        # Добавляем фрейм в canvas
        left_canvas_window = left_canvas.create_window((0, 0), window=left_frame, anchor="nw", width=330)

        # Настройка прокрутки колесиком мыши
        def _on_mousewheel_left(event):
            left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        left_canvas.bind("<Enter>", lambda e: left_canvas.bind_all("<MouseWheel>", _on_mousewheel_left))
        left_canvas.bind("<Leave>", lambda e: left_canvas.unbind_all("<MouseWheel>"))

        # Упаковываем canvas и scrollbar
        left_canvas.pack(side="left", fill="both", expand=True)
        left_scrollbar.pack(side="right", fill="y")

        # Правая панель - изображение (без прокрутки)
        right_frame = ttk.Frame(main_paned)
        main_paned.add(right_frame, weight=3)

        self._setup_left_panel(left_frame)  # теперь передаем left_frame, а не left_container
        self._setup_right_panel(right_frame)

        # Панель статуса внизу
        self._setup_status_bar()

        # Обновляем ширину canvas_window при изменении размера
        def _configure_left_canvas(event):
            left_canvas.itemconfig(left_canvas_window, width=left_canvas.winfo_width() - 5)

        left_canvas.bind("<Configure>", _configure_left_canvas)

    def _setup_left_panel(self, parent):
        """Левая панель с управлением"""
        # Заголовок
        title = ttk.Label(parent, text="Управление парковкой",
                          font=('Arial', 14, 'bold'))
        title.pack(pady=10)

        # ===== Управление камерами =====
        camera_frame = ttk.LabelFrame(parent, text="Камеры", padding=10)
        camera_frame.pack(fill=tk.X, padx=10, pady=5)

        # Список камер
        list_frame = ttk.Frame(camera_frame)
        list_frame.pack(fill=tk.X, pady=5)

        self.camera_listbox = tk.Listbox(list_frame, height=5)
        self.camera_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL,
                                  command=self.camera_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.camera_listbox.config(yscrollcommand=scrollbar.set)

        self.camera_listbox.bind('<<ListboxSelect>>', self._on_camera_select)

        # Кнопки управления камерами
        btn_frame = ttk.Frame(camera_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame, text="➕ Добавить",
                   command=self._add_camera_dialog).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        ttk.Button(btn_frame, text="✏️ Редакт.",
                   command=self._edit_camera_dialog).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        ttk.Button(btn_frame, text="🗑️ Удалить",
                   command=self._delete_camera).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        # ===== Информация о камере =====
        self.info_frame = ttk.LabelFrame(parent, text="Информация о камере", padding=10)
        self.info_frame.pack(fill=tk.X, padx=10, pady=5)

        self.cam_info_text = tk.Text(self.info_frame, height=6, width=40, wrap=tk.WORD)
        self.cam_info_text.pack(fill=tk.X, pady=5)
        self.cam_info_text.insert(1.0, "Камера не выбрана")
        self.cam_info_text.config(state=tk.DISABLED)

        # ===== Парковочные места =====
        container_frame = ttk.LabelFrame(parent, text="Парковочные места", padding=10)
        container_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Список мест
        list_frame2 = ttk.Frame(container_frame)
        list_frame2.pack(fill=tk.BOTH, expand=True, pady=5)

        self.container_listbox = tk.Listbox(list_frame2, height=8)
        self.container_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar2 = ttk.Scrollbar(list_frame2, orient=tk.VERTICAL,
                                   command=self.container_listbox.yview)
        scrollbar2.pack(side=tk.RIGHT, fill=tk.Y)
        self.container_listbox.config(yscrollcommand=scrollbar2.set)

        self.container_listbox.bind('<<ListboxSelect>>', self._on_container_select)

        # Кнопки управления местами
        btn_frame2 = ttk.Frame(container_frame)
        btn_frame2.pack(fill=tk.X, pady=5)

        ttk.Button(btn_frame2, text="➕ Новое",
                   command=self._start_draw_container).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        ttk.Button(btn_frame2, text="✏️ Править",
                   command=self._edit_container).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)
        ttk.Button(btn_frame2, text="🗑️ Удалить",
                   command=self._delete_container).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)

        # ===== Параметры места =====
        size_frame = ttk.LabelFrame(parent, text="Параметры места (метры)", padding=10)
        size_frame.pack(fill=tk.X, padx=10, pady=5)

        grid = ttk.Frame(size_frame)
        grid.pack(fill=tk.X)

        ttk.Label(grid, text="Длина:").grid(row=0, column=0, sticky=tk.W, pady=2)
        self.length_var = tk.DoubleVar(value=5.0)
        length_spin = ttk.Spinbox(grid, from_=1.0, to=20.0, increment=0.1,
                                  textvariable=self.length_var, width=10)
        length_spin.grid(row=0, column=1, pady=2, padx=5)
        length_spin.bind('<KeyRelease>', self._on_param_change)

        ttk.Label(grid, text="Ширина:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.width_var = tk.DoubleVar(value=2.5)
        width_spin = ttk.Spinbox(grid, from_=1.0, to=10.0, increment=0.1,
                                 textvariable=self.width_var, width=10)
        width_spin.grid(row=1, column=1, pady=2, padx=5)
        width_spin.bind('<KeyRelease>', self._on_param_change)

        ttk.Label(grid, text="Высота:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.height_var = tk.DoubleVar(value=2.0)
        height_spin = ttk.Spinbox(grid, from_=0.5, to=5.0, increment=0.1,
                                  textvariable=self.height_var, width=10)
        height_spin.grid(row=2, column=1, pady=2, padx=5)
        height_spin.bind('<KeyRelease>', self._on_param_change)

        # ===== Кнопки сохранения =====
        save_frame = ttk.LabelFrame(parent, text="Действия с БД", padding=10)
        save_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(save_frame, text="💾 Сохранить все изменения",
                   command=self._save_all_to_db).pack(fill=tk.X, pady=2)
        ttk.Button(save_frame, text="🔄 Отменить изменения",
                   command=self._revert_changes).pack(fill=tk.X, pady=2)
        ttk.Button(save_frame, text="🔄 Загрузить из БД",
                   command=self._load_from_db).pack(fill=tk.X, pady=2)

    def _setup_right_panel(self, parent):
        """Правая панель с изображением"""
        # Панель инструментов
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill=tk.X, pady=5)

        self.mode_var = tk.StringVar(value="view")

        ttk.Radiobutton(toolbar, text="👁️ Просмотр", variable=self.mode_var,
                        value="view", command=self._set_mode_view).pack(side=tk.LEFT, padx=2)
        ttk.Radiobutton(toolbar, text="✏️ Рисовать", variable=self.mode_var,
                        value="draw", command=self._set_mode_draw).pack(side=tk.LEFT, padx=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, padx=10, fill=tk.Y)

        ttk.Button(toolbar, text="❌ Очистить", command=self._clear_drawing).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="✅ Готово", command=self._finish_editing).pack(side=tk.LEFT, padx=2)

        # Индикатор несохраненных изменений
        self.unsaved_label = ttk.Label(toolbar, text="", foreground="red")
        self.unsaved_label.pack(side=tk.RIGHT, padx=10)

        # Холст для изображения
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg='#2b2b2b', cursor="crosshair")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Привязка событий
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_release)
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

    def _setup_status_bar(self):
        """Панель статуса внизу"""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, side=tk.BOTTOM, padx=5, pady=2)

        self.status_var = tk.StringVar(value="Готов")
        status_label = ttk.Label(status_frame, textvariable=self.status_var,
                                 relief=tk.SUNKEN, anchor=tk.W)
        status_label.pack(fill=tk.X)

        self.coord_var = tk.StringVar(value="")
        coord_label = ttk.Label(status_frame, textvariable=self.coord_var,
                                relief=tk.SUNKEN, width=30)
        coord_label.pack(side=tk.RIGHT)

    # ===== Загрузка данных из БД =====

    def _load_cameras(self):
        """Загружает список камер из БД"""
        self.camera_listbox.delete(0, tk.END)
        cameras = self.db.get_all_cameras()

        for cam in cameras:
            display_text = f"{cam.id}: {cam.name}"
            if cam.location:
                display_text += f" ({cam.location})"
            self.camera_listbox.insert(tk.END, display_text)

    def _on_camera_select(self, event):
        """Выбор камеры из списка"""
        selection = self.camera_listbox.curselection()
        if not selection:
            return

        # Проверяем несохраненные изменения
        if self.has_unsaved_changes:
            if not messagebox.askyesno("Несохраненные изменения",
                                       "Есть несохраненные изменения. Переключить камеру?"):
                # Сбрасываем выделение
                self.camera_listbox.selection_clear(0, tk.END)
                return

        # Получаем ID камеры
        text = self.camera_listbox.get(selection[0])
        camera_id = int(text.split(':')[0])

        self.current_camera_id = camera_id
        self._load_camera_data(camera_id)

    def _load_camera_data(self, camera_id: int):
        """Загружает данные для камеры"""
        # Получаем информацию о камере
        camera = self.db.get_camera(camera_id)
        if not camera:
            return

        self.current_camera_info = {
            'id': camera.id,
            'name': camera.name,
            'video_path': camera.video_path,
            'location': camera.location,
            'segments_config_id': camera.segments_config_id
        }

        # Обновляем информацию
        self.cam_info_text.config(state=tk.NORMAL)
        self.cam_info_text.delete(1.0, tk.END)
        self.cam_info_text.insert(1.0,
                                  f"ID: {camera.id}\n"
                                  f"Название: {camera.name}\n"
                                  f"Расположение: {camera.location or 'не указано'}\n"
                                  f"Видео: {os.path.basename(camera.video_path) if camera.video_path else 'нет'}"
                                  )
        self.cam_info_text.config(state=tk.DISABLED)

        # Создаем временную сцену
        self._create_temp_scene(camera_id)

        # Загружаем изображение
        self._load_camera_image()

    def _create_temp_scene(self, camera_id: int):
        """Создает временную 3D сцену с контейнерами из БД"""
        self.temp_scene = Scene3D()

        # Загружаем контейнеры для этой камеры
        containers = self.db.get_camera_containers(camera_id)

        for container in containers:
            # Восстанавливаем калибровку, если это базовый контейнер
            if container.is_base:
                camera_data = self.db.get_camera_data(container.id)
                if camera_data:
                    # Создаем калибровку
                    calibration = CameraCalibration(
                        camera_matrix=camera_data.camera_matrix,
                        dist_coeffs=camera_data.dist_coeffs,
                        image_shape=camera_data.image_shape
                    )
                    self.temp_scene.set_camera_calibration(calibration)

                    # Восстанавливаем параметры PnP (их нужно добавить в таблицу)
                    # Пока оставим как есть - Scene3D их пересчитает при необходимости

                    self.image_shape = camera_data.image_shape

            # Создаем контейнер из данных БД
            container_3d = ParkingContainer3D(
                id=container.id,
                name=container.name,
                ground_corners=np.array(container.ground_points),
                upper_corners=np.array(container.upper_points),
                image_points=np.array(container.image_points) if container.image_points else None,
                length=container.length,
                width=container.width,
                height=container.height
            )

            # Добавляем в сцену
            self.temp_scene.containers[container.id] = container_3d

            # Если это базовый, запоминаем
            if container.is_base:
                self.temp_scene.base_container_id = container.id

        # Обновляем список мест в GUI
        self._update_container_listbox()

        self.has_unsaved_changes = False
        self._update_unsaved_indicator()

    def _update_container_listbox(self):
        """Обновляет список мест в GUI"""
        self.container_listbox.delete(0, tk.END)

        if not self.temp_scene:
            return

        for container_id, container in self.temp_scene.containers.items():
            base_mark = " [BASE]" if container_id == self.temp_scene.base_container_id else ""
            display_text = f"{container_id}: {container.name}{base_mark} ({container.length:.1f}x{container.width:.1f})"
            self.container_listbox.insert(tk.END, display_text)

    def _load_camera_image(self):
        """Загружает первый кадр с камеры"""
        if not self.current_camera_info:
            return

        video_path = self.current_camera_info['video_path']
        if not video_path or not os.path.exists(video_path):
            self.status_var.set(f"Видеофайл не найден: {video_path}")
            return

        try:
            cap = cv2.VideoCapture(video_path)
            ret, frame = cap.read()
            cap.release()

            if ret:
                self.original_image = frame
                self.current_image = frame.copy()
                self.image_shape = (frame.shape[1], frame.shape[0])  # width, height
                self._refresh_view()
                self.status_var.set(f"Изображение загружено: {os.path.basename(video_path)}")
            else:
                self.status_var.set("Не удалось прочитать кадр из видео")
        except Exception as e:
            self.status_var.set(f"Ошибка загрузки изображения: {e}")

    # ===== Отображение =====

    def _refresh_view(self):
        """Обновляет отображение изображения"""
        if self.current_image is None:
            return

        self._display_image()

    def _display_image(self):
        """Отображает изображение на холсте"""
        if self.current_image is None:
            return

        # Конвертируем в RGB
        image_rgb = cv2.cvtColor(self.current_image, cv2.COLOR_BGR2RGB)
        image_pil = Image.fromarray(image_rgb)

        # Получаем размеры холста
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width > 10 and canvas_height > 10:
            # Масштабируем с сохранением пропорций
            img_ratio = image_pil.width / image_pil.height
            canvas_ratio = canvas_width / canvas_height

            if img_ratio > canvas_ratio:
                new_width = canvas_width
                new_height = int(canvas_width / img_ratio)
                self.image_offset_x = 0
                self.image_offset_y = (canvas_height - new_height) // 2
            else:
                new_height = canvas_height
                new_width = int(canvas_height * img_ratio)
                self.image_offset_x = (canvas_width - new_width) // 2
                self.image_offset_y = 0

            self.scale_x = new_width / self.current_image.shape[1]
            self.scale_y = new_height / self.current_image.shape[0]

            image_pil = image_pil.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Отображаем
            self.canvas_photo = ImageTk.PhotoImage(image_pil)
            self.canvas.delete("all")
            self.canvas.create_image(self.image_offset_x, self.image_offset_y,
                                     anchor=tk.NW, image=self.canvas_photo)

            # Рисуем контейнеры из временной сцены
            self._draw_containers()

            # Рисуем текущие точки рисования
            self._draw_drawing_points()

    def _draw_containers(self):
        """Рисует контейнеры из временной сцены"""
        if not self.temp_scene:
            return

        for container_id, container in self.temp_scene.containers.items():
            if container.image_points is None:
                continue

            points = container.image_points

            # Масштабируем точки
            canvas_points = []
            for x, y in points:
                canvas_x = x * self.scale_x + self.image_offset_x
                canvas_y = y * self.scale_y + self.image_offset_y
                canvas_points.extend([canvas_x, canvas_y])

            # Выбираем цвет (без альфа-канала)
            if container_id == self.temp_scene.base_container_id:
                outline = "#00ff00"  # зеленый для базового
                fill = "#00ff00"  # заливка зеленым (без прозрачности)
            else:
                outline = "#ffaa00"  # оранжевый для обычных
                fill = "#ffaa00"  # заливка оранжевым

            # Если это редактируемый контейнер, рисуем по-другому
            if self.mode == "edit_container" and self.editing_container_id == container_id:
                outline = "#ffff00"  # желтый для редактируемого
                fill = "#ffff00"  # заливка желтым

            # Рисуем полигон
            self.canvas.create_polygon(canvas_points, outline=outline, fill=fill,
                                       width=3 if container_id == self.editing_container_id else 2,
                                       stipple="gray50",  # добавляем штриховку для полупрозрачности
                                       tags=f"container_{container_id}")

            # Рисуем точки
            for i, (x, y) in enumerate(points):
                canvas_x = x * self.scale_x + self.image_offset_x
                canvas_y = y * self.scale_y + self.image_offset_y

                # Размер точки зависит от режима
                radius = 8 if (self.mode == "edit_container" and
                               self.editing_container_id == container_id) else 5

                self.canvas.create_oval(canvas_x - radius, canvas_y - radius,
                                        canvas_x + radius, canvas_y + radius,
                                        fill="white", outline=outline, width=2,
                                        tags=f"point_{container_id}_{i}")

                # Номер точки
                if self.mode == "edit_container" and self.editing_container_id == container_id:
                    self.canvas.create_text(canvas_x + 15, canvas_y - 15,
                                            text=str(i + 1), fill="white",
                                            font=('Arial', 10, 'bold'),
                                            tags=f"text_{container_id}_{i}")

            # Название контейнера
            center_x = np.mean([p[0] for p in points]) * self.scale_x + self.image_offset_x
            center_y = np.mean([p[1] for p in points]) * self.scale_y + self.image_offset_y

            self.canvas.create_text(center_x, center_y - 20,
                                    text=f"{container.name}", fill=outline,
                                    font=('Arial', 12, 'bold'),
                                    tags=f"label_{container_id}")

    def _draw_drawing_points(self):
        """Рисует точки в процессе рисования"""
        if not self.drawing_points or self.mode not in ["draw", "edit_container"]:
            return

        self.canvas.delete("drawing")

        for i, (x, y) in enumerate(self.drawing_points):
            canvas_x = x * self.scale_x + self.image_offset_x
            canvas_y = y * self.scale_y + self.image_offset_y

            # Разные цвета для разных режимов
            if self.mode == "draw":
                color = "#ffff00"  # желтый для нового
            else:
                color = "#00ffff"  # голубой для редактирования

            self.canvas.create_oval(canvas_x - 10, canvas_y - 10,
                                    canvas_x + 10, canvas_y + 10,
                                    fill=color, outline="white", width=2,
                                    tags="drawing")

            self.canvas.create_text(canvas_x + 20, canvas_y - 20,
                                    text=str(i + 1), fill=color,
                                    font=('Arial', 12, 'bold'),
                                    tags="drawing")

        if len(self.drawing_points) == 4:
            # Рисуем полигон
            canvas_points = []
            for x, y in self.drawing_points:
                canvas_x = x * self.scale_x + self.image_offset_x
                canvas_y = y * self.scale_y + self.image_offset_y
                canvas_points.extend([canvas_x, canvas_y])

            color = "#ffff00" if self.mode == "draw" else "#00ffff"
            self.canvas.create_polygon(canvas_points, outline=color,
                                       fill="", width=3, tags="drawing")

    # ===== Режимы работы =====

    def _set_mode_view(self):
        """Режим просмотра"""
        self.mode = "view"
        self.drawing_points = []
        self.editing_container_id = None
        self.canvas.config(cursor="crosshair")
        self.status_var.set("Режим просмотра")
        self._refresh_view()

    def _set_mode_draw(self):
        """Режим рисования нового контейнера"""
        if not self.temp_scene:
            messagebox.showwarning("Предупреждение", "Сначала выберите камеру")
            self.mode_var.set("view")
            return

        # Если есть незавершенное редактирование, спрашиваем
        if self.mode == "edit_container":
            if not messagebox.askyesno("Режим рисования",
                                       "Закончить редактирование и начать рисование нового места?"):
                self.mode_var.set("edit")
                return

        self.mode = "draw"
        self.drawing_points = []
        self.editing_container_id = None
        self.canvas.config(cursor="pencil")
        self.status_var.set("Режим рисования: выберите 4 точки (по часовой стрелке)")
        self._refresh_view()

    def _start_draw_container(self):
        """Начинает рисование нового контейнера"""
        self.mode_var.set("draw")
        self._set_mode_draw()

    def _edit_container(self):
        """Редактирование выбранного контейнера"""
        selection = self.container_listbox.curselection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Сначала выберите место")
            return

        if not self.temp_scene:
            return

        # Получаем ID контейнера
        text = self.container_listbox.get(selection[0])
        container_id = int(text.split(':')[0])

        container = self.temp_scene.containers.get(container_id)
        if not container or container.image_points is None:
            messagebox.showwarning("Предупреждение", "У контейнера нет 2D точек для редактирования")
            return

        self.mode = "edit_container"
        self.editing_container_id = container_id
        self.drawing_points = container.image_points.tolist()

        # Устанавливаем размеры
        self.length_var.set(container.length)
        self.width_var.set(container.width)
        self.height_var.set(container.height)

        self.mode_var.set("edit")
        self.canvas.config(cursor="hand2")
        self.status_var.set(f"Редактирование места {container_id}. Перетаскивайте точки")
        self._refresh_view()

    def _delete_container(self):
        """Удаление контейнера из временной сцены"""
        selection = self.container_listbox.curselection()
        if not selection:
            messagebox.showwarning("Предупреждение", "Сначала выберите место")
            return

        text = self.container_listbox.get(selection[0])
        container_id = int(text.split(':')[0])

        if messagebox.askyesno("Подтверждение", f"Удалить место {container_id}?"):
            # Удаляем из временной сцены
            if container_id in self.temp_scene.containers:
                del self.temp_scene.containers[container_id]

                # Если это был базовый, сбрасываем
                if container_id == self.temp_scene.base_container_id:
                    self.temp_scene.base_container_id = None

            self._update_container_listbox()
            self.has_unsaved_changes = True
            self._update_unsaved_indicator()
            self._refresh_view()
            self.status_var.set(f"Место {container_id} удалено (несохранено)")

    def _finish_editing(self):
        """Завершает редактирование текущего контейнера"""
        if self.mode == "draw" and len(self.drawing_points) == 4:
            # Создаем новый контейнер
            self._create_container_from_points()
        elif self.mode == "edit_container" and len(self.drawing_points) == 4:
            # Обновляем существующий
            self._update_container_from_points()
        else:
            self._set_mode_view()

    def _create_container_from_points(self):
        """Создает новый контейнер используя Scene3D"""
        if len(self.drawing_points) != 4:
            messagebox.showwarning("Предупреждение", "Нужно выбрать 4 точки")
            return

        # Спрашиваем имя
        name = tk.simpledialog.askstring("Имя места", "Введите название места (например A12):",
                                         parent=self.root)
        if not name:
            return

        length = self.length_var.get()
        width = self.width_var.get()
        height = self.height_var.get()

        try:
            # Проверяем, есть ли уже базовый контейнер
            if self.temp_scene.base_container_id is None:
                # Это будет базовый контейнер
                is_base = messagebox.askyesno("Базовый контейнер",
                                              "Это первое место. Сделать его базовым?\n"
                                              "(Базовый контейнер определяет систему координат)")
                if is_base:
                    # Сначала устанавливаем калибровку камеры по умолчанию
                    if self.image_shape and not self.temp_scene.camera_calibration:
                        calib = CameraCalibration.create_default(self.image_shape)
                        self.temp_scene.set_camera_calibration(calib)

                    # Создаем базовый контейнер
                    container_id = self.temp_scene.create_base_container(
                        image_points=np.array(self.drawing_points),
                        length=length,
                        width=width,
                        height=height,
                        name=name
                    )
                    self.status_var.set(f"Базовый контейнер {name} создан")
                else:
                    messagebox.showwarning("Предупреждение",
                                           "Сначала нужно создать базовый контейнер")
                    return
            else:
                # Создаем обычный контейнер
                container_id = self.temp_scene.create_container(
                    image_points=np.array(self.drawing_points),
                    length=length,
                    width=width,
                    height=height,
                    name=name
                )
                self.status_var.set(f"Контейнер {name} создан")

            self._update_container_listbox()
            self.has_unsaved_changes = True
            self._update_unsaved_indicator()
            self._set_mode_view()

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось создать контейнер: {e}")
            import traceback
            traceback.print_exc()

    def _update_container_from_points(self):
        """Обновляет существующий контейнер используя Scene3D"""
        if not self.editing_container_id:
            return

        length = self.length_var.get()
        width = self.width_var.get()
        height = self.height_var.get()

        try:
            # Обновляем контейнер через Scene3D
            success = self.temp_scene.update_container(
                container_id=self.editing_container_id,
                image_points=np.array(self.drawing_points),
                length=length,
                width=width,
                height=height
            )

            if success:
                self._update_container_listbox()
                self.has_unsaved_changes = True
                self._update_unsaved_indicator()
                self._set_mode_view()
                self.status_var.set(f"Контейнер обновлен")
            else:
                messagebox.showerror("Ошибка", "Не удалось обновить контейнер")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось обновить контейнер: {e}")

    def _clear_drawing(self):
        """Очищает текущее рисование"""
        self.drawing_points = []
        self.canvas.delete("drawing")
        self.status_var.set("Рисование отменено")

    # ===== Работа с БД =====

    def _save_all_to_db(self):
        """Сохраняет все изменения из временной сцены в БД"""
        if not self.temp_scene or not self.current_camera_id:
            return

        if not self.has_unsaved_changes:
            messagebox.showinfo("Информация", "Нет несохраненных изменений")
            return

        try:
            # Получаем текущие контейнеры из БД
            db_containers = {c.id: c for c in self.db.get_camera_containers(self.current_camera_id)}

            # Сохраняем/обновляем контейнеры из временной сцены
            for container_id, container in self.temp_scene.containers.items():
                # Подготовка данных
                ground_points = container.ground_corners.tolist() if container.ground_corners is not None else []
                upper_points = container.upper_corners.tolist() if container.upper_corners is not None else []
                image_points = container.image_points.tolist() if container.image_points is not None else []
                is_base = (container_id == self.temp_scene.base_container_id)

                if container_id < 0 or container_id not in db_containers:
                    # Новый контейнер
                    db_container = self.db.add_parking_container(
                        camera_id=self.current_camera_id,
                        name=container.name,
                        length=container.length,
                        width=container.width,
                        height=container.height,
                        ground_points=ground_points,
                        upper_points=upper_points,
                        image_points=image_points,
                        is_base=is_base
                    )

                    # Если это базовый и есть калибровка, сохраняем её
                    if is_base and self.temp_scene.camera_calibration:
                        calib = self.temp_scene.camera_calibration
                        # Нужно получить rvec, tvec из Scene3D
                        # Пока пропускаем - доработаем позже

                else:
                    # Существующий контейнер - обновляем
                    self.db.update_parking_container(
                        container_id=container_id,
                        name=container.name,
                        length=container.length,
                        width=container.width,
                        height=container.height,
                        ground_points=ground_points,
                        upper_points=upper_points
                    )

                    # Удаляем из словаря, чтобы потом удалить лишние
                    db_containers.pop(container_id, None)

            # Удаляем контейнеры, которых нет во временной сцене
            for old_id in db_containers.keys():
                self.db.delete_parking_container(old_id)

            self.has_unsaved_changes = False
            self._update_unsaved_indicator()

            # Перезагружаем сцену из БД для синхронизации ID
            self._create_temp_scene(self.current_camera_id)

            self.status_var.set("Изменения сохранены в БД")
            messagebox.showinfo("Успех", "Все изменения сохранены")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось сохранить изменения: {e}")
            import traceback
            traceback.print_exc()

    def _revert_changes(self):
        """Отменяет все изменения и загружает из БД"""
        if not self.current_camera_id:
            return

        if self.has_unsaved_changes:
            if messagebox.askyesno("Подтверждение",
                                   "Отменить все несохраненные изменения?"):
                self._create_temp_scene(self.current_camera_id)
                self._refresh_view()
                self.status_var.set("Изменения отменены")

    def _load_from_db(self):
        """Принудительно загружает данные из БД"""
        if not self.current_camera_id:
            return

        if self.has_unsaved_changes:
            if not messagebox.askyesno("Подтверждение",
                                       "Есть несохраненные изменения. Загрузить из БД?"):
                return

        self._create_temp_scene(self.current_camera_id)
        self._refresh_view()
        self.status_var.set("Данные загружены из БД")

    def _on_param_change(self, event=None):
        """Обработчик изменения параметров"""
        if self.mode == "edit_container" and self.editing_container_id:
            # В реальном времени обновляем размеры в контейнере
            container = self.temp_scene.containers.get(self.editing_container_id)
            if container:
                container.length = self.length_var.get()
                container.width = self.width_var.get()
                container.height = self.height_var.get()
                self.has_unsaved_changes = True
                self._update_unsaved_indicator()

    def _update_unsaved_indicator(self):
        """Обновляет индикатор несохраненных изменений"""
        if self.has_unsaved_changes:
            self.unsaved_label.config(text="✗ Несохранено")
        else:
            self.unsaved_label.config(text="")

    # ===== Обработчики событий мыши =====

    def _on_canvas_click(self, event):
        """Клик на холсте"""
        if self.mode == "view":
            # Показываем координаты
            x = (event.x - self.image_offset_x) / self.scale_x
            y = (event.y - self.image_offset_y) / self.scale_y
            if self.original_image is not None and 0 <= x < self.original_image.shape[1] and 0 <= y < \
                    self.original_image.shape[0]:
                self.coord_var.set(f"({x:.1f}, {y:.1f})")
            return

        # Переводим координаты
        x = (event.x - self.image_offset_x) / self.scale_x
        y = (event.y - self.image_offset_y) / self.scale_y

        if self.original_image is None:
            return

        if not (0 <= x < self.original_image.shape[1] and 0 <= y < self.original_image.shape[0]):
            return

        if self.mode in ["draw", "edit_container"]:
            # Проверяем, не кликнули ли на точку для перетаскивания
            if self.drawing_points:
                for i, (px, py) in enumerate(self.drawing_points):
                    dist = np.sqrt((x - px) ** 2 + (y - py) ** 2)
                    if dist < 20:  # порог в пикселях
                        self.dragging_point = True
                        self.dragging_point_idx = i
                        return

            # Если не на точку и режим рисования - добавляем новую
            if self.mode == "draw" and len(self.drawing_points) < 4:
                self.drawing_points.append((x, y))
                self.status_var.set(f"Точка {len(self.drawing_points)}/4")
                self._draw_drawing_points()

    def _on_canvas_drag(self, event):
        """Перетаскивание мыши"""
        if self.dragging_point_idx is not None:
            x = (event.x - self.image_offset_x) / self.scale_x
            y = (event.y - self.image_offset_y) / self.scale_y

            if self.original_image is not None:
                x = max(0, min(x, self.original_image.shape[1] - 1))
                y = max(0, min(y, self.original_image.shape[0] - 1))

            if 0 <= self.dragging_point_idx < len(self.drawing_points):
                self.drawing_points[self.dragging_point_idx] = (x, y)
                self._draw_drawing_points()
                self.has_unsaved_changes = True
                self._update_unsaved_indicator()

    def _on_canvas_release(self, event):
        """Отпускание мыши"""
        self.dragging_point = False
        self.dragging_point_idx = None

    def _on_mousewheel(self, event):
        """Колесико мыши - масштабирование (пока не реализовано)"""
        pass

    def _on_canvas_configure(self, event):
        """Изменение размера холста"""
        self._display_image()

    def _on_container_select(self, event):
        """Выбор контейнера из списка"""
        pass

    # ===== Диалоги управления камерами =====

    def _add_camera_dialog(self):
        """Диалог добавления камеры"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Добавить камеру")
        dialog.geometry("500x450")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Название камеры:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(main_frame, width=40)
        name_entry.grid(row=0, column=1, pady=5)

        ttk.Label(main_frame, text="Путь к видео:").grid(row=1, column=0, sticky=tk.W, pady=5)
        path_frame = ttk.Frame(main_frame)
        path_frame.grid(row=1, column=1, pady=5)
        path_entry = ttk.Entry(path_frame, width=30)
        path_entry.pack(side=tk.LEFT)
        ttk.Button(path_frame, text="Обзор",
                   command=lambda: path_entry.insert(0, filedialog.askopenfilename())).pack(side=tk.LEFT, padx=5)

        ttk.Label(main_frame, text="Расположение:").grid(row=2, column=0, sticky=tk.W, pady=5)
        loc_entry = ttk.Entry(main_frame, width=40)
        loc_entry.grid(row=2, column=1, pady=5)

        ttk.Label(main_frame, text="Конфигурация сегментов:").grid(row=3, column=0, sticky=tk.W, pady=5)

        configs = self.db.get_all_segments_configs()
        config_names = [c.name for c in configs]

        config_combo = ttk.Combobox(main_frame, values=config_names, width=37)
        config_combo.grid(row=3, column=1, pady=5)
        if config_names:
            config_combo.set(config_names[0])

        def save():
            name = name_entry.get().strip()
            path = path_entry.get().strip()
            location = loc_entry.get().strip()
            config_name = config_combo.get()

            if not name or not path:
                messagebox.showwarning("Предупреждение", "Заполните обязательные поля")
                return

            config_id = None
            for c in configs:
                if c.name == config_name:
                    config_id = c.id
                    break

            try:
                self.db.add_camera(
                    video_path=path,
                    name=name,
                    segments_config_id=config_id,
                    location=location
                )
                dialog.destroy()
                self._load_cameras()
                self.status_var.set(f"Камера {name} добавлена")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

        ttk.Button(main_frame, text="Сохранить", command=save).grid(row=4, column=0, columnspan=2, pady=20)

    def _edit_camera_dialog(self):
        """Редактирование камеры"""
        if not self.current_camera_id:
            messagebox.showwarning("Предупреждение", "Сначала выберите камеру")
            return

        camera = self.db.get_camera(self.current_camera_id)
        if not camera:
            return

        dialog = tk.Toplevel(self.root)
        dialog.title("Редактировать камеру")
        dialog.geometry("500x400")
        dialog.transient(self.root)
        dialog.grab_set()

        main_frame = ttk.Frame(dialog, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Название камеры:").grid(row=0, column=0, sticky=tk.W, pady=5)
        name_entry = ttk.Entry(main_frame, width=40)
        name_entry.insert(0, camera.name)
        name_entry.grid(row=0, column=1, pady=5)

        ttk.Label(main_frame, text="Путь к видео:").grid(row=1, column=0, sticky=tk.W, pady=5)
        path_frame = ttk.Frame(main_frame)
        path_frame.grid(row=1, column=1, pady=5)
        path_entry = ttk.Entry(path_frame, width=30)
        path_entry.insert(0, camera.video_path)
        path_entry.pack(side=tk.LEFT)
        ttk.Button(path_frame, text="Обзор",
                   command=lambda: path_entry.insert(0, filedialog.askopenfilename())).pack(side=tk.LEFT, padx=5)

        ttk.Label(main_frame, text="Расположение:").grid(row=2, column=0, sticky=tk.W, pady=5)
        loc_entry = ttk.Entry(main_frame, width=40)
        loc_entry.insert(0, camera.location or "")
        loc_entry.grid(row=2, column=1, pady=5)

        def save():
            name = name_entry.get().strip()
            path = path_entry.get().strip()
            location = loc_entry.get().strip()

            if not name or not path:
                messagebox.showwarning("Предупреждение", "Заполните обязательные поля")
                return

            try:
                self.db.update_camera(
                    camera_id=self.current_camera_id,
                    name=name,
                    video_path=path,
                    location=location
                )
                dialog.destroy()
                self._load_cameras()
                self._load_camera_data(self.current_camera_id)
                self.status_var.set(f"Камера {name} обновлена")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

        ttk.Button(main_frame, text="Сохранить", command=save).grid(row=3, column=0, columnspan=2, pady=20)

    def _delete_camera(self):
        """Удаление камеры"""
        if not self.current_camera_id:
            messagebox.showwarning("Предупреждение", "Сначала выберите камеру")
            return

        if messagebox.askyesno("Подтверждение",
                               f"Удалить камеру {self.current_camera_id}?\n"
                               "Все связанные места тоже будут удалены."):
            try:
                self.db.delete_camera(self.current_camera_id)
                self.current_camera_id = None
                self.temp_scene = None
                self.current_image = None
                self.original_image = None
                self._load_cameras()
                self._refresh_view()
                self.status_var.set("Камера удалена")
            except Exception as e:
                messagebox.showerror("Ошибка", str(e))

    # ===== 3D визуализация =====

    def _show_3d(self):
        """Показывает 3D визуализацию текущей сцены"""
        if not self.temp_scene or not self.temp_scene.containers:
            messagebox.showwarning("Предупреждение", "Нет данных для визуализации")
            return

        # Запускаем в отдельном потоке
        def run_visualization():
            try:
                from parking_monitor.core.garage_3d import MultiContainerVisualizer
                vis = MultiContainerVisualizer(self.temp_scene)
                vis.run_visualization()
            except Exception as e:
                print(f"Error in 3D visualization: {e}")

        threading.Thread(target=run_visualization, daemon=True).start()

    # ===== Работа с JSON =====

    def _save_markup(self):
        """Сохраняет разметку в JSON файл"""
        if not self.temp_scene:
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )

        if file_path:
            data = {
                'camera_id': self.current_camera_id,
                'image_shape': self.image_shape,
                'base_container_id': self.temp_scene.base_container_id,
                'containers': {}
            }

            for cid, container in self.temp_scene.containers.items():
                data['containers'][str(cid)] = {
                    'name': container.name,
                    'length': container.length,
                    'width': container.width,
                    'height': container.height,
                    'image_points': container.image_points.tolist() if container.image_points is not None else [],
                    'ground_points': container.ground_corners.tolist() if container.ground_corners is not None else [],
                    'upper_points': container.upper_corners.tolist() if container.upper_corners is not None else [],
                    'is_base': cid == self.temp_scene.base_container_id
                }

            with open(file_path, 'w') as f:
                json.dump(data, f, indent=2)

            self.status_var.set(f"Разметка сохранена в {file_path}")

    def _load_markup(self):
        """Загружает разметку из JSON файла"""
        file_path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")]
        )

        if not file_path:
            return

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            # Создаем временную сцену
            self.temp_scene = Scene3D()
            self.image_shape = tuple(data['image_shape']) if data['image_shape'] else None

            # Восстанавливаем контейнеры
            for cid_str, cont_data in data['containers'].items():
                cid = int(cid_str)

                container = ParkingContainer3D(
                    id=cid,
                    name=cont_data['name'],
                    ground_corners=np.array(cont_data.get('ground_points', [])),
                    upper_corners=np.array(cont_data.get('upper_points', [])),
                    image_points=np.array(cont_data['image_points']) if cont_data['image_points'] else None,
                    length=cont_data['length'],
                    width=cont_data['width'],
                    height=cont_data['height']
                )
                self.temp_scene.containers[cid] = container

                if cont_data.get('is_base', False):
                    self.temp_scene.base_container_id = cid

            self._update_container_listbox()
            self.has_unsaved_changes = True
            self._update_unsaved_indicator()
            self._refresh_view()
            self.status_var.set(f"Разметка загружена из {file_path}")

        except Exception as e:
            messagebox.showerror("Ошибка", f"Не удалось загрузить разметку: {e}")
            import traceback
            traceback.print_exc()

    def _load_image(self):
        """Загружает изображение для разметки"""
        file_path = filedialog.askopenfilename(
            filetypes=[("Image files", "*.jpg *.jpeg *.png *.bmp")]
        )

        if file_path:
            image = cv2.imread(file_path)
            if image is not None:
                self.original_image = image
                self.current_image = image.copy()
                self.image_shape = (image.shape[1], image.shape[0])
                self._refresh_view()
                self.status_var.set(f"Изображение загружено: {os.path.basename(file_path)}")

if __name__ == "__main__":
    from parking_monitor.main import create_db_pool
    # Создаем пул соединений
    db_pool = create_db_pool()
    # Создаем репозиторий
    repo = ParkingRepository(db_pool)
    # Запускаем GUI
    root = tk.Tk()
    app = AdminGUI(root, repo)

    root.mainloop()