from typing import Dict


class FindStorage:
    def __init__(self):
        self.searched: Dict[int, list] = {}
        self.found: Dict[int, list] = {}

    def vehicle_found(self, vehicle_id: int):
        self.found[vehicle_id] = self.searched[vehicle_id]
        self.searched.pop(vehicle_id)

    def vehicle_lost(self, vehicle_id: int):
        print(f"ДОБАВИЛ {vehicle_id} обратно в searched")
        self.searched[vehicle_id] = self.found[vehicle_id]
        self.found.pop(vehicle_id)
