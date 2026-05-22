import numpy as np
import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
from parking_monitor.core.scene3d import Scene3D


def save_normalized_coordinates(points, image_height, image_width):
    normalized = []
    for x, y in points:
        norm_x = x / image_width
        norm_y = y / image_height
        normalized.append((norm_x, norm_y))
    return normalized


def restore_coordinates(normalized_points, new_height, new_width):
    restored = []
    for norm_x, norm_y in normalized_points:
        x = norm_x * new_width
        y = norm_y * new_height
        restored.append((x, y))
    return restored


class MultiContainerVisualizer:
    """Визуализатор нескольких контейнеров с поддержкой анимации автомобилей."""

    def __init__(self, scene: Scene3D):
        self.scene = scene
        self.screen = None
        self.rotation_x = 0
        self.rotation_y = 0
        self.translation_z = -20
        self.dragging = False
        self.last_mouse_pos = None

        # Для анимации
        self.paused = False
        self.frame_delay = 50  # мс между кадрами
        self.last_frame_time = 0

        # Настройки отображения
        self.show_contours = True
        self.show_centers = True
        self.show_centers_at_height = True
        self.show_trails = True
        self.show_directions = True
        self.trail_length = 10

    def init_gl(self, width=1200, height=800):
        pygame.init()
        self.screen = pygame.display.set_mode((width, height), DOUBLEBUF | OPENGL)
        pygame.display.set_caption(
            "3D Parking with Cars - SPACE: pause, LEFT/RIGHT: step, +/-: speed, "
            "1/2/3/4: toggle layers, C: center, R: reset view"
        )

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)
        glEnable(GL_COLOR_MATERIAL)

        glLightfv(GL_LIGHT0, GL_POSITION, (10, 10, 10, 1))
        glLightfv(GL_LIGHT0, GL_AMBIENT, (0.3, 0.3, 0.3, 1))
        glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.7, 0.7, 0.7, 1))

        glMatrixMode(GL_PROJECTION)
        gluPerspective(45, width / height, 0.1, 500.0)
        glMatrixMode(GL_MODELVIEW)

    def draw_grid(self, size=50, step=5):
        glPushAttrib(GL_ENABLE_BIT | GL_LIGHTING_BIT)
        glDisable(GL_LIGHTING)

        glBegin(GL_LINES)
        glColor3f(0.4, 0.4, 0.4)
        for i in range(-size, size + 1, step):
            glVertex3f(i, 0, -size)
            glVertex3f(i, 0, size)
            glVertex3f(-size, 0, i)
            glVertex3f(size, 0, i)
        glEnd()

        # Оси
        glLineWidth(2)
        glBegin(GL_LINES)
        glColor3f(1, 0, 0)
        glVertex3f(0, 0, 0)
        glVertex3f(size, 0, 0)
        glColor3f(0, 0, 1)
        glVertex3f(0, 0, 0)
        glVertex3f(0, 0, size)
        glColor3f(0, 1, 0)
        glVertex3f(0, 0, 0)
        glVertex3f(0, size, 0)
        glEnd()

        glPopAttrib()

    def draw_containers(self):
        """Рисует контейнеры - теперь доступ к данным проще"""
        colors = [
            ((0, 1, 0), (0, 0, 1), (1, 0, 0)),
            ((0, 1, 1), (1, 0, 1), (1, 1, 0)),
            ((1, 0.65, 0), (0.5, 0, 0.5), (0, 0.5, 0.5)),
        ]

        for i, (container_id, container) in enumerate(self.scene.containers.items()):
            color_idx = i % len(colors)
            ground_color, upper_color, vertical_color = colors[color_idx]

            # Используем свойства container напрямую
            glBegin(GL_LINE_LOOP)
            glColor3f(*ground_color)
            for point in container.ground_corners:
                glVertex3f(point[0], point[1], point[2])
            glEnd()

            # Верхняя плоскость
            glBegin(GL_LINE_LOOP)
            glColor3f(*upper_color)
            for point in container.upper_corners:
                glVertex3f(point[0], point[1], point[2])
            glEnd()

            # Вертикальные рёбра
            glBegin(GL_LINES)
            glColor3f(*vertical_color)
            for j in range(4):
                glVertex3f(container.ground_corners[j][0],
                           container.ground_corners[j][1],
                           container.ground_corners[j][2])
                glVertex3f(container.upper_corners[j][0],
                           container.upper_corners[j][1],
                           container.upper_corners[j][2])
            glEnd()

            # Полупрозрачные грани
            glEnable(GL_BLEND)
            glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

            glBegin(GL_QUADS)
            glColor4f(ground_color[0], ground_color[1], ground_color[2], 0.1)
            for point in container.ground_corners:
                glVertex3f(point[0], point[1], point[2])
            glEnd()

            glBegin(GL_QUADS)
            glColor4f(upper_color[0], upper_color[1], upper_color[2], 0.1)
            for point in container.upper_corners:
                glVertex3f(point[0], point[1], point[2])
            glEnd()

            glDisable(GL_BLEND)

    def draw_car_projections(self):
        """Рисует проекции автомобилей текущего кадра."""
        current_frame = self.scene.get_current_frame()
        if not current_frame or not current_frame.cars:
            return

        glPushAttrib(GL_ENABLE_BIT | GL_LIGHTING_BIT | GL_COLOR_BUFFER_BIT)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        # Цвета для разных автомобилей
        car_colors = [
            (0.0, 0.8, 0.0, 0.4),  # Зеленый
            (0.8, 0.0, 0.0, 0.4),  # Красный
            (0.0, 0.0, 0.8, 0.4),  # Синий
            (0.8, 0.8, 0.0, 0.4),  # Желтый
            (0.8, 0.0, 0.8, 0.4),  # Пурпурный
            (0.0, 0.8, 0.8, 0.4),  # Голубой
        ]

        contour_colors = [
            (0.0, 1.0, 0.0, 1.0),  # Ярко-зеленый
            (1.0, 0.0, 0.0, 1.0),  # Ярко-красный
            (0.0, 0.0, 1.0, 1.0),  # Ярко-синий
            (1.0, 1.0, 0.0, 1.0),  # Ярко-желтый
            (1.0, 0.0, 1.0, 1.0),  # Ярко-пурпурный
            (0.0, 1.0, 1.0, 1.0),  # Ярко-голубой
        ]

        for car_idx, car in enumerate(current_frame.cars):
            color = car_colors[car_idx % len(car_colors)]
            contour_color = contour_colors[car_idx % len(contour_colors)]

            # Упрощённо: рисуем сферу в центре
            if self.show_centers_at_height and car.center is not None:
                glPushMatrix()
                glTranslatef(
                    car.center[0],
                    car.center[1],
                    car.center[2]
                )

                quad = gluNewQuadric()
                glColor4f(contour_color[0], contour_color[1], contour_color[2], 0.8)
                gluSphere(quad, 0.15, 12, 12)
                gluDeleteQuadric(quad)

                glPopMatrix()

                # Рисуем вектор направления
                if self.show_directions and car.direction is not None:
                    end_point = car.center + car.direction * 1.5
                    self.draw_direction_arrow(
                        car.center,
                        end_point,
                        contour_color[:3]
                    )

        glPopAttrib()

    def draw_direction_arrow(self, start_point, end_point, color):
        """Рисует стрелку направления в 3D"""
        glPushAttrib(GL_ENABLE_BIT | GL_LIGHTING_BIT | GL_LINE_BIT)
        glDisable(GL_LIGHTING)
        glLineWidth(3)

        # Основная линия
        glBegin(GL_LINES)
        glColor3f(*color)
        glVertex3f(start_point[0], start_point[1], start_point[2])
        glVertex3f(end_point[0], end_point[1], end_point[2])
        glEnd()

        # Наконечник стрелки
        direction = end_point - start_point
        direction_norm = direction / np.linalg.norm(direction)

        perp1 = np.cross(direction_norm, [0, 1, 0])
        if np.linalg.norm(perp1) < 0.1:
            perp1 = np.cross(direction_norm, [1, 0, 0])
        perp1 = perp1 / np.linalg.norm(perp1)

        perp2 = np.cross(direction_norm, perp1)
        perp2 = perp2 / np.linalg.norm(perp2)

        arrow_size = min(0.5, np.linalg.norm(direction) * 0.2)
        tip_back = end_point - direction_norm * arrow_size * 0.5

        glBegin(GL_TRIANGLES)
        glColor3f(*color)
        # Первое крыло
        glVertex3f(end_point[0], end_point[1], end_point[2])
        glVertex3f(tip_back[0] + perp1[0] * arrow_size * 0.3,
                   tip_back[1] + perp1[1] * arrow_size * 0.3,
                   tip_back[2] + perp1[2] * arrow_size * 0.3)
        glVertex3f(tip_back[0] - perp1[0] * arrow_size * 0.3,
                   tip_back[1] - perp1[1] * arrow_size * 0.3,
                   tip_back[2] - perp1[2] * arrow_size * 0.3)

        # Второе крыло
        glVertex3f(end_point[0], end_point[1], end_point[2])
        glVertex3f(tip_back[0] + perp2[0] * arrow_size * 0.3,
                   tip_back[1] + perp2[1] * arrow_size * 0.3,
                   tip_back[2] + perp2[2] * arrow_size * 0.3)
        glVertex3f(tip_back[0] - perp2[0] * arrow_size * 0.3,
                   tip_back[1] - perp2[1] * arrow_size * 0.3,
                   tip_back[2] - perp2[2] * arrow_size * 0.3)
        glEnd()

        glPopAttrib()

    def draw_car_trails(self):
        """Рисует следы движения центров автомобилей."""
        if not self.show_trails or len(self.scene.frames) < 2:
            return

        glPushAttrib(GL_ENABLE_BIT | GL_LIGHTING_BIT)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        start_frame = max(0, self.scene.current_frame_index - self.trail_length)

        for frame_offset in range(start_frame, self.scene.current_frame_index + 1):
            frame = self.scene.get_frame(frame_offset)
            if not frame:
                continue

            alpha = 0.2 + 0.6 * (frame_offset - start_frame) / (self.scene.current_frame_index - start_frame + 1)

            for car in frame.cars:
                glPointSize(4)
                glBegin(GL_POINTS)
                glColor4f(0.5, 0.5, 0.5, alpha)
                glVertex3f(car.center[0],
                           car.center[1],
                           car.center[2])
                glEnd()

        glPopAttrib()

    def draw_debug_points(self):
        """Рисует отладочные 3D точки"""
        if not self.scene.debug_points:
            return

        glPushAttrib(GL_ENABLE_BIT | GL_LIGHTING_BIT | GL_COLOR_BUFFER_BIT)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        point_colors = [(1, 0, 1), (1, 0.5, 0), (0, 1, 1)]

        for i, point in enumerate(self.scene.debug_points):
            x, y, z = point
            color_idx = i % len(point_colors)
            color = point_colors[color_idx]

            glPointSize(10)
            glBegin(GL_POINTS)
            glColor3f(*color)
            glVertex3f(x, y, z)
            glEnd()

            glBegin(GL_LINES)
            glColor3f(*color)
            glVertex3f(x, y, z)
            glVertex3f(x, 0, z)
            glEnd()

        glPopAttrib()

    def handle_events(self):
        current_time = pygame.time.get_ticks()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    self.dragging = True
                    self.last_mouse_pos = pygame.mouse.get_pos()
                elif event.button == 4:
                    self.translation_z += 1.0
                elif event.button == 5:
                    self.translation_z -= 1.0
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    self.dragging = False
            elif event.type == pygame.MOUSEMOTION and self.dragging:
                current_pos = pygame.mouse.get_pos()
                if self.last_mouse_pos:
                    dx = current_pos[0] - self.last_mouse_pos[0]
                    dy = current_pos[1] - self.last_mouse_pos[1]
                    self.rotation_y += dx * 0.5
                    self.rotation_x += dy * 0.5
                self.last_mouse_pos = current_pos
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                elif event.key == pygame.K_r:
                    self.rotation_x = 0
                    self.rotation_y = 0
                    self.translation_z = -20
                elif event.key == pygame.K_c:
                    self.center_on_containers()
                elif event.key == pygame.K_SPACE:
                    self.paused = not self.paused
                elif event.key == pygame.K_LEFT:
                    self.scene.prev_frame()
                elif event.key == pygame.K_RIGHT:
                    self.scene.next_frame()
                elif event.key == pygame.K_PLUS or event.key == pygame.K_EQUALS:
                    self.frame_delay = max(10, self.frame_delay - 10)
                elif event.key == pygame.K_MINUS:
                    self.frame_delay = min(500, self.frame_delay + 10)
                elif event.key == pygame.K_1:
                    self.show_contours = not self.show_contours
                elif event.key == pygame.K_2:
                    self.show_centers = not self.show_centers
                elif event.key == pygame.K_3:
                    self.show_centers_at_height = not self.show_centers_at_height
                elif event.key == pygame.K_4:
                    self.show_trails = not self.show_trails
                elif event.key == pygame.K_5:
                    self.show_directions = not self.show_directions

        if not self.paused and self.scene.frames:
            if current_time - self.last_frame_time > self.frame_delay:
                self.scene.next_frame()
                self.last_frame_time = current_time

        return True

    def center_on_containers(self):
        if not self.scene.containers:
            return

        all_points = []
        for container in self.scene.containers.values():
            all_points.extend(container.ground_corners)
            all_points.extend(container.upper_corners)

        if all_points:
            all_points = np.array(all_points)
            center = np.mean(all_points, axis=0)
            max_extent = np.max(np.abs(all_points - center))
            self.translation_z = -max_extent * 3
            self.rotation_x = -30
            self.rotation_y = 45

    def render(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        glTranslatef(0, 0, self.translation_z)
        glRotatef(self.rotation_x, 1, 0, 0)
        glRotatef(self.rotation_y, 0, 1, 0)

        self.draw_grid()
        self.draw_containers()
        self.draw_car_projections()

        self.draw_hud()

        pygame.display.flip()

    def draw_hud(self):
        """Отображает информацию на экране."""
        glPushAttrib(GL_ENABLE_BIT | GL_LIGHTING_BIT)
        glDisable(GL_LIGHTING)

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        w, h = pygame.display.get_surface().get_size()
        glOrtho(0, w, h, 0, -1, 1)

        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        font = pygame.font.Font(None, 24)

        info_lines = [
            f"Frame: {self.scene.current_frame_index + 1}/{len(self.scene.frames)}",
            f"Paused: {'Yes' if self.paused else 'No'}",
            f"Speed: {1000 / self.frame_delay:.1f} fps",
            f"Contours: {'ON' if self.show_contours else 'OFF'} (1)",
            f"Centers@0.5m: {'ON' if self.show_centers_at_height else 'OFF'} (3)",
            f"Directions: {'ON' if self.show_directions else 'OFF'} (5)",
            f"Trails: {'ON' if self.show_trails else 'OFF'} (4)",
            f"Cars in frame: {len(self.scene.get_current_frame().cars) if self.scene.get_current_frame() else 0}"
        ]

        y = 20
        for line in info_lines:
            text_surface = font.render(line, True, (255, 255, 255))
            text_data = pygame.image.tostring(text_surface, "RGBA", True)
            glWindowPos2d(10, y)
            glDrawPixels(text_surface.get_width(), text_surface.get_height(),
                         GL_RGBA, GL_UNSIGNED_BYTE, text_data)
            y += 25

        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)
        glPopMatrix()

        glPopAttrib()

    def run_visualization(self):
        """Запускает визуализацию"""
        self.init_gl()
        self.center_on_containers()

        clock = pygame.time.Clock()
        running = True
        while running:
            running = self.handle_events()
            self.render()
            clock.tick(60)

        pygame.quit()