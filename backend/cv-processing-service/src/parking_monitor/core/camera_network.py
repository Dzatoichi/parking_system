# core/camera_network.py

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, Any
import json


@dataclass
class CameraNode:
    """Узел в сети камер"""
    id: int
    name: str
    segments_config_id: int
    horizontal_segments: int = 8  # по умолчанию
    vertical_segments: int = 5  # по умолчанию

    def get_all_segments(self) -> List[str]:
        """Возвращает все возможные сегменты для этой камеры"""
        segments = []

        # Верхние и нижние сегменты (горизонтальные)
        for i in range(1, self.horizontal_segments + 1):
            segments.append(f"top_{i}")
            segments.append(f"bottom_{i}")

        # Левые и правые сегменты (вертикальные)
        for i in range(1, self.vertical_segments + 1):
            segments.append(f"left_{i}")
            segments.append(f"right_{i}")

        return segments

    def validate_segment(self, segment: str) -> bool:
        """Проверяет, существует ли такой сегмент"""
        import re
        pattern = r'^(top|bottom|left|right)_(\d+)$'
        match = re.match(pattern, segment)

        if not match:
            return False

        side, num_str = match.groups()
        num = int(num_str)

        if side in ['top', 'bottom']:
            return 1 <= num <= self.horizontal_segments
        else:  # left, right
            return 1 <= num <= self.vertical_segments


@dataclass
class CameraConnection:
    """Связь между камерами"""
    source_camera: int
    source_segment: str
    target_camera: int
    target_segment: str
    bidirectional: bool = True
    weight: float = 1.0  # вероятность/вес связи (можно использовать несколько вариантов)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CameraNetwork:
    """
    Сеть камер с сегментацией.
    Хранит связи между камерами и предоставляет методы для навигации.
    """

    def __init__(self):
        # Граф связей: (source_cam, source_seg) -> list of (target_cam, target_seg, bidirectional, weight)
        self.graph: Dict[Tuple[int, str], List[Tuple[int, str, bool, float]]] = {}

        # Индекс для обратных связей (быстрый поиск)
        self.reverse_index: Dict[Tuple[int, str], List[Tuple[int, str, bool, float]]] = {}

        # Кэш узлов (информация о камерах)
        self.nodes: Dict[int, CameraNode] = {}

        # Статистика
        self.stats = {
            'total_connections': 0,
            'bidirectional_count': 0
        }

    def add_node(self, camera_id: int, name: str, segments_config_id: int,
                 h_segments: int = 8, v_segments: int = 5):
        """Добавляет узел (камеру) в сеть"""
        self.nodes[camera_id] = CameraNode(
            id=camera_id,
            name=name,
            segments_config_id=segments_config_id,
            horizontal_segments=h_segments,
            vertical_segments=v_segments
        )

    def add_connection(self,
                       source_camera: int,
                       source_segment: str,
                       target_camera: int,
                       target_segment: str,
                       bidirectional: bool = True,
                       weight: float = 1.0) -> bool:
        """
        Добавляет связь между камерами.
        Возвращает True, если связь добавлена.
        """
        # Проверяем, что камеры существуют
        if source_camera not in self.nodes or target_camera not in self.nodes:
            print(f"CameraNetwork: cannot add connection - camera not found")
            return False

        # Проверяем сегменты
        source_node = self.nodes[source_camera]
        target_node = self.nodes[target_camera]

        if not source_node.validate_segment(source_segment):
            print(f"CameraNetwork: invalid source segment {source_segment} for camera {source_camera}")
            return False

        if not target_node.validate_segment(target_segment):
            print(f"CameraNetwork: invalid target segment {target_segment} for camera {target_camera}")
            return False

        # Добавляем прямую связь
        key = (source_camera, source_segment)
        if key not in self.graph:
            self.graph[key] = []

        # Проверяем, нет ли уже такой связи
        for existing in self.graph[key]:
            if existing[0] == target_camera and existing[1] == target_segment:
                print(f"CameraNetwork: connection already exists")
                return False

        self.graph[key].append((target_camera, target_segment, bidirectional, weight))
        self.stats['total_connections'] += 1

        if bidirectional:
            self.stats['bidirectional_count'] += 1

        # Добавляем в обратный индекс
        rev_key = (target_camera, target_segment)
        if rev_key not in self.reverse_index:
            self.reverse_index[rev_key] = []
        self.reverse_index[rev_key].append((source_camera, source_segment, bidirectional, weight))

        # Если двунаправленная, добавляем и обратную связь в граф
        if bidirectional:
            rev_key_in_graph = (target_camera, target_segment)
            if rev_key_in_graph not in self.graph:
                self.graph[rev_key_in_graph] = []
            self.graph[rev_key_in_graph].append((source_camera, source_segment, bidirectional, weight))

        print(f"CameraNetwork: added connection {source_camera}:{source_segment} -> "
              f"{target_camera}:{target_segment} (bidirectional={bidirectional})")
        return True

    def remove_connection(self, source_camera: int, source_segment: str,
                          target_camera: int, target_segment: str) -> bool:
        """Удаляет конкретную связь"""
        key = (source_camera, source_segment)
        if key not in self.graph:
            return False

        original_len = len(self.graph[key])
        self.graph[key] = [
            conn for conn in self.graph[key]
            if not (conn[0] == target_camera and conn[1] == target_segment)
        ]

        removed = len(self.graph[key]) < original_len

        if removed:
            self.stats['total_connections'] -= 1

            # Удаляем из обратного индекса
            rev_key = (target_camera, target_segment)
            if rev_key in self.reverse_index:
                self.reverse_index[rev_key] = [
                    conn for conn in self.reverse_index[rev_key]
                    if not (conn[0] == source_camera and conn[1] == source_segment)
                ]

            # Если связь была двунаправленной, удаляем и обратную
            # Проверяем по сохраненным данным или просто пробуем удалить
            self.graph[rev_key] = [
                conn for conn in self.graph.get(rev_key, [])
                if not (conn[0] == source_camera and conn[1] == source_segment)
            ]

        return removed

    def get_next_cameras(self, camera_id: int, segment: str) -> List[Tuple[int, str]]:
        """
        Возвращает список камер, в которые можно попасть из данного сегмента.
        Учитывает только прямые связи (source -> target).
        """
        key = (camera_id, segment)
        if key not in self.graph:
            return []

        result = []
        for target_cam, target_seg, bidirectional, weight in self.graph[key]:
            result.append((target_cam, target_seg))

        return result

    def get_previous_cameras(self, camera_id: int, segment: str) -> List[Tuple[int, str]]:
        """
        Возвращает список камер, из которых можно попасть в данный сегмент.
        """
        key = (camera_id, segment)
        if key not in self.reverse_index:
            return []

        result = []
        for source_cam, source_seg, bidirectional, weight in self.reverse_index[key]:
            result.append((source_cam, source_seg))

        return result

    def get_all_connections(self, camera_id: int) -> Dict[str, List[Tuple[int, str, str]]]:
        """
        Возвращает все связи для камеры, сгруппированные по сегментам.
        Возвращает: {
            "top_3": [(2, "bottom_1", "outgoing"), (4, "left_2", "incoming")],
            ...
        }
        """
        result = {}

        # Исходящие связи
        for (src_cam, src_seg), targets in self.graph.items():
            if src_cam == camera_id:
                if src_seg not in result:
                    result[src_seg] = []
                for target_cam, target_seg, bidirectional, weight in targets:
                    result[src_seg].append((target_cam, target_seg, "outgoing"))

        # Входящие связи (через reverse_index)
        for (tgt_cam, tgt_seg), sources in self.reverse_index.items():
            if tgt_cam == camera_id:
                if tgt_seg not in result:
                    result[tgt_seg] = []
                for src_cam, src_seg, bidirectional, weight in sources:
                    # Проверяем, не добавлена ли уже эта связь как исходящая
                    already_added = False
                    for existing in result[tgt_seg]:
                        if existing[0] == src_cam and existing[1] == src_seg and existing[2] == "outgoing":
                            already_added = True
                            break

                    if not already_added:
                        result[tgt_seg].append((src_cam, src_seg, "incoming"))

        return result

    def find_path(self, from_camera: int, from_segment: str,
                  to_camera: int, to_segment: Optional[str] = None,
                  max_depth: int = 5) -> List[Tuple[int, str]]:
        """
        Находит путь от одного сегмента к другому (простой BFS).
        Возвращает список (camera_id, segment) включая начальный и конечный.
        """
        from collections import deque

        # BFS
        queue = deque()
        queue.append((from_camera, from_segment, [(from_camera, from_segment)]))
        visited = set()
        visited.add((from_camera, from_segment))

        while queue:
            cam, seg, path = queue.popleft()

            # Проверяем, достигли ли цели
            if cam == to_camera:
                if to_segment is None or seg == to_segment:
                    return path

            if len(path) >= max_depth:
                continue

            # Смотрим все исходящие связи
            key = (cam, seg)
            if key in self.graph:
                for next_cam, next_seg, bidirectional, weight in self.graph[key]:
                    if (next_cam, next_seg) not in visited:
                        visited.add((next_cam, next_seg))
                        new_path = path + [(next_cam, next_seg)]
                        queue.append((next_cam, next_seg, new_path))

        return []  # путь не найден

    def get_all_possible_destinations(self, camera_id: int, segment: str) -> Set[Tuple[int, str]]:
        """
        Возвращает все возможные места назначения из данного сегмента
        (прямые связи + обратные bidirectional)
        """
        result = set()

        # Прямые связи
        key = (camera_id, segment)
        if key in self.graph:
            for target_cam, target_seg, bidirectional, weight in self.graph[key]:
                result.add((target_cam, target_seg))

        # Обратные связи (если они bidirectional, то из них тоже можно попасть)
        # Но это уже другой случай - это значит, что из этого сегмента можно попасть
        # в те камеры, которые имеют связь с этим сегментом
        if key in self.reverse_index:
            for source_cam, source_seg, bidirectional, weight in self.reverse_index[key]:
                if bidirectional:
                    # Если связь двунаправленная, то из текущего сегмента можно попасть
                    # в исходный сегмент исходной камеры
                    result.add((source_cam, source_seg))

        return result

    def load_from_db(self, db_repo):
        """
        Загружает сеть из базы данных.
        Ожидает, что у db_repo есть методы:
        - get_all_cameras()
        - get_all_camera_connections()
        - get_segments_config(config_id)
        """
        # Загружаем камеры
        cameras = db_repo.get_all_cameras()
        for cam in cameras:
            # Получаем конфигурацию сегментов
            config = db_repo.get_segments_config(cam.segments_config_id)
            if config:
                self.add_node(
                    camera_id=cam.id,
                    name=cam.name,
                    segments_config_id=config.id,
                    h_segments=config.horizontal_segments,
                    v_segments=config.vertical_segments
                )
            else:
                # Значения по умолчанию
                self.add_node(
                    camera_id=cam.id,
                    name=cam.name,
                    segments_config_id=0,
                    h_segments=8,
                    v_segments=5
                )

        # Загружаем связи
        connections = db_repo.get_all_camera_connections()
        for conn in connections:
            self.add_connection(
                source_camera=conn.source_camera_id,
                source_segment=conn.source_segment,
                target_camera=conn.target_camera_id,
                target_segment=conn.target_segment,
                bidirectional=conn.bidirectional
            )

    def to_dict(self) -> Dict:
        """Сериализует сеть в словарь (для сохранения)"""
        result = {
            'nodes': {},
            'connections': []
        }

        for cam_id, node in self.nodes.items():
            result['nodes'][cam_id] = {
                'name': node.name,
                'segments_config_id': node.segments_config_id,
                'horizontal_segments': node.horizontal_segments,
                'vertical_segments': node.vertical_segments
            }

        for (src_cam, src_seg), targets in self.graph.items():
            for tgt_cam, tgt_seg, bidirectional, weight in targets:
                result['connections'].append({
                    'source_camera': src_cam,
                    'source_segment': src_seg,
                    'target_camera': tgt_cam,
                    'target_segment': tgt_seg,
                    'bidirectional': bidirectional,
                    'weight': weight
                })

        return result

    def save_to_db(self, db_repo):
        """
        Сохраняет сеть в базу данных.
        Нужно реализовать в зависимости от структуры БД.
        """
        # TODO: реализовать сохранение
        pass

    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику сети"""
        return {
            'total_cameras': len(self.nodes),
            'total_connections': self.stats['total_connections'],
            'bidirectional_count': self.stats['bidirectional_count'],
            'cameras': list(self.nodes.keys())
        }

    def validate_network(self) -> List[str]:
        """
        Проверяет целостность сети.
        Возвращает список проблем.
        """
        issues = []

        # Проверяем, что все сегменты в связях валидны
        for (cam_id, seg) in self.graph.keys():
            if cam_id not in self.nodes:
                issues.append(f"Camera {cam_id} in connections but not in nodes")
                continue

            node = self.nodes[cam_id]
            if not node.validate_segment(seg):
                issues.append(f"Invalid segment {seg} for camera {cam_id}")

        # Проверяем обратные связи
        for (cam_id, seg) in self.reverse_index.keys():
            if cam_id not in self.nodes:
                issues.append(f"Camera {cam_id} in reverse index but not in nodes")
                continue

            node = self.nodes[cam_id]
            if not node.validate_segment(seg):
                issues.append(f"Invalid segment {seg} in reverse index for camera {cam_id}")

        # Проверяем симметричность bidirectional связей
        for (src_cam, src_seg), targets in self.graph.items():
            for tgt_cam, tgt_seg, bidirectional, weight in targets:
                if bidirectional:
                    # Должна быть обратная связь
                    rev_key = (tgt_cam, tgt_seg)
                    found = False
                    if rev_key in self.graph:
                        for rev_tgt_cam, rev_tgt_seg, rev_bidirectional, rev_weight in self.graph[rev_key]:
                            if rev_tgt_cam == src_cam and rev_tgt_seg == src_seg:
                                found = True
                                break

                    if not found:
                        issues.append(
                            f"Bidirectional connection {src_cam}:{src_seg} -> "
                            f"{tgt_cam}:{tgt_seg} has no reverse link"
                        )

        return issues