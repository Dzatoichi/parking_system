import axios from "axios";

export const pmApi = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});
export const emulatorApi = axios.create({
  baseURL: "/emulator",
  headers: { "Content-Type": "application/json" },
});
export const cvApiClient = axios.create({
  baseURL: "/cv",
  headers: { "Content-Type": "application/json" },
});

pmApi.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error?.response) {
      // eslint-disable-next-line no-console
      console.error("API error", {
        status: error.response.status,
        data: error.response.data,
        url: error.config?.url,
      });
    } else {
      // eslint-disable-next-line no-console
      console.error("Network error", error?.message);
    }
    return Promise.reject(error);
  }
);

export type PaginatedResponse<T> = {
  items: T[];
  total: number;
  page: number;
  size: number;
};

export type ParkingRead = {
  id: number;
  name: string;
  address: string;
  total_spots: number;
  available_spots: number;
  is_active: boolean;
};

export type ParkingStats = {
  parking_id: number;
  total_spots: number;
  free: number;
  occupied: number;
  reserved: number;
  occupancy_rate: number;
  avg_duration_minutes: number | null;
};

export type CameraStatus = "active" | "inactive" | "maintenance" | "error";

export type CameraRead = {
  id: number;
  rtsp_url: string;
  status: CameraStatus;
  position_x: number | null;
  position_y: number | null;
  is_calibrated: boolean;
  parking_id: number;
  monitored_spot_ids: number[];
};

export type CameraNetworkRead = {
  parking_id: number;
  cameras: CameraRead[];
  total: number;
};

export type CVMonitoringStatus = {
  mode: "idle" | "markup" | "monitoring";
  running: boolean;
  monitor: {
    cameras: number;
    active_processors: number;
    active_vehicles: number;
    parked_vehicles: number;
    total_vehicles: number;
    stats: Record<string, number>;
  } | null;
};

export type Point3D = [number, number, number];
export type Point2D = [number, number];

export type ParkingSceneContainer = {
  id: number;
  camera_id: number;
  spot_id?: number | null;
  name: string;
  length: number;
  width: number;
  height: number;
  ground_points: Point3D[];
  upper_points: Point3D[];
  image_points?: Point2D[] | null;
  is_base?: boolean;
  polygon: Point2D[];
  occupied?: boolean;
  parked_since?: string | null;
};

export type ParkingSceneVehicle = {
  track_id: number;
  center: Point3D;
  direction?: Point3D | null;
  container_id?: number;
};

export type ParkingScene = {
  camera_id: number;
  bbox: [number, number, number, number];
  containers: ParkingSceneContainer[];
  spots: ParkingSceneContainer[];
  vehicles: ParkingSceneVehicle[];
};

export type MarkupContainerPayload = {
  id?: number | null;
  spot_id?: number | null;
  name: string;
  length: number;
  width: number;
  height: number;
  ground_points?: Point3D[] | null;
  upper_points?: Point3D[] | null;
  image_points?: Point2D[] | null;
  is_base?: boolean;
};

export type MarkupSceneResponse = {
  mode: "markup";
  camera_id: number;
  containers: ParkingSceneContainer[];
};

export type ParkingScenesResponse = {
  type: "all_scenes";
  data: Record<string, ParkingScene>;
};

export type CameraCreate = {
  rtsp_url: string;
  position_x?: number | null;
  position_y?: number | null;
  is_calibrated?: boolean;
  monitored_spot_ids?: number[];
};

export type CameraUpdate = Partial<{
  rtsp_url: string;
  status: CameraStatus;
  position_x: number | null;
  position_y: number | null;
  is_calibrated: boolean;
}>;

export type BookingStatus = 'pending' | 'confirmed' | 'completed' | 'cancelled' | 'expired';

export type BookingRead = {
  id: number;
  spot_id: number;
  spot_number: string | null;
  user_id: number;
  user_name: string | null;
  vehicle_plate_number: string | null;
  start_time: string;
  end_time: string;
  status: BookingStatus;
  created_at: string;
  updated_at: string;
};

export type SpotStatus = "free" | "occupied" | "reserved";
export type SpotType = "standard" | "disabled";

export type SpotReadShort = {
  id: number;
  spot_number: string;
  spot_type: SpotType;
  spot_status: SpotStatus;
  current_vehicle_id: number | null;
};

export type SpotCoordinates = {
  points: number[][];
  center_x: number;
  center_y: number;
};

export type SpotRead = SpotReadShort & {
  spot_coordinates: SpotCoordinates;
  parking_id: number;
};

export type VehicleRead = {
  id: number;
  plate_number: string;
  is_inside: boolean;
  is_blocked: boolean;
  last_seen: string | null;
  last_camera_id: number | null;
};

export type TrackingEventRead = {
  id: number;
  camera_id: number;
  spot_id: number | null;
  event_type: string;
  timestamp: string;
};

export type VehicleRouteRead = {
  vehicle_id: number;
  plate_number: string;
  events: TrackingEventRead[];
  total_events: number;
};

export type AnalyticsOverview = {
  parking_id: number;
  total_spots: number;
  free_spots: number;
  occupied_spots: number;
  occupancy_rate: number;
  avg_duration_minutes: number;
  peak_occupancy_percent: number;
  unique_visitors_week: number;
  total_entries_today: number;
  total_exits_today: number;
  current_vehicles: number;
  peak_hour: string;
  hourly_traffic: { hour: string; vehicles: number }[];
  weekly_occupancy: { day: string; occupancy: number }[];
  duration_distribution: { name: string; value: number; color: string }[];
  recent_events: { type: string; plate: string; time: string; action: string }[];
  mini_spots: { id: number; status: "free" | "occupied"; plate: string | null }[];
}

export type DeviceStateOut = {
  parking_id: number;
  barrier: { position: "open" | "closed" };
  lighting: { on: boolean; brightness: number};
}

export type CommandResultOut = {
  success: boolean;
  parking_id: number;
  device_kind: string;
  action: string;
  state: Record<string, unknown>;
  message: string | null;
}

export type LightingSetBody = {
  on: boolean;
  brightness: number;
  simulate_unreachable: boolean;
}

export const parkingApi = {
  getAll: (params?: { only_active?: boolean; page?: number; size?: number }) =>
    pmApi.get<PaginatedResponse<ParkingRead>>("/parking", { params }),
};

export const cameraApi = {
  getByParking: (parkingId: number) =>
    pmApi.get<CameraNetworkRead>(`/cameras/${parkingId}`),
  create: (parkingId: number, body: CameraCreate) =>
    pmApi.post<CameraRead>(`/cameras/${parkingId}`, body),
  update: (cameraId: number, body: CameraUpdate) =>
    pmApi.patch<CameraRead>(`/cameras/${cameraId}`, body),
  delete: (cameraId: number) => pmApi.delete(`/cameras/${cameraId}`),
};

export const spotApi = {
  getByParking: (parkingId: number, params?: { page?: number; size?: number }) =>
    pmApi.get<PaginatedResponse<SpotReadShort>>(`/spots/${parkingId}`, {
      params,
    }),
  getMap: (parkingId: number) =>
    pmApi.get<SpotRead[]>(`/spots/${parkingId}/map`),
  getStats: (parkingId: number) => pmApi.get<ParkingStats>(`/spots/${parkingId}/stats`),
  getDetail: (spotId: number) => pmApi.get<SpotRead>(`/spots/detail/${spotId}`),
  create: (parkingId: number, body: { spot_number: string; spot_type?: SpotType; spot_coordinates: SpotCoordinates }) =>
    pmApi.post<SpotRead>(`/spots/${parkingId}`, body),
  updateCoordinates: (spotId: number, body: { spot_coordinates: SpotCoordinates }) =>
    pmApi.patch<SpotRead>(`/spots/${spotId}/coordinates`, body),
  delete: (spotId: number) => pmApi.delete(`/spots/${spotId}`),
};

export const vehicleApi = {
  getAll: (params?: { only_inside?: boolean; page?: number; size?: number }) =>
    pmApi.get<PaginatedResponse<VehicleRead>>("/vehicles", { params }),
  getById: (id: number) =>
    pmApi.get<VehicleRead>(`/vehicles/${id}`),
  getByPlate: (plateNumber: string) =>
    pmApi.get<VehicleRead>(`/vehicles/by-plate/${encodeURIComponent(plateNumber)}`),
  getHistory: (vehicleId: number, params?: { limit?: number }) =>
    pmApi.get<VehicleRouteRead>(`/vehicles/${vehicleId}/history`, { params }),
  setBlockByPlate: (plateNumber: string, blocked: boolean) =>
    pmApi.patch<VehicleRead>(`/vehicles/by-plate/${encodeURIComponent(plateNumber)}/block`, { blocked }),
};

export const analyticsApi = {
  getOverview: (parkingId: number) =>
    pmApi.get<AnalyticsOverview>(`/analytics/${parkingId}/overview`),
};

export const bookingApi = {
  getAll: (params: {
    parking_id?: number;
    status?: BookingStatus;
    vehicle_plate?: string;
    from?: string;
    to?: string;
    start_date?: string;
    end_date?: string;
    start_from?: string;
    start_to?: string;
    end_from?: string;
    end_to?: string;
    page?: number;
    size?: number;
  }) => pmApi.get<PaginatedResponse<BookingRead>>("/bookings", { params }),
};

export const DeviceApi = {
  getDevicesState: (parkingId: number) =>
    emulatorApi.get<DeviceStateOut>(`/v1/parking/${parkingId}/devices/state`),

  openBarrier: (params: { parkingId: number; simulate_unreachable?: boolean }) =>
    emulatorApi.post<CommandResultOut>(
      `/v1/parking/${params.parkingId}/devices/barrier/open`,
      null,
      { params: { simulate_unreachable: params.simulate_unreachable ?? false } }
    ),

  closeBarrier: (params: { parkingId: number; simulate_unreachable?: boolean }) =>
    emulatorApi.post<CommandResultOut>(
      `/v1/parking/${params.parkingId}/devices/barrier/close`,
      null,
      { params: { simulate_unreachable: params.simulate_unreachable ?? false } }
    ),

  setLighting: (params: { parkignId: number; body: LightingSetBody }) =>
    emulatorApi.post<CommandResultOut>(
      `/v1/parking/${params.parkignId}/devices/lighting`,
      params.body
    ),
};

export const cvMonitoringApi = {
  getStatus: () => cvApiClient.get<CVMonitoringStatus>("/v1/monitoring/status"),
  getScenes: () => cvApiClient.get<ParkingScenesResponse>("/v1/monitoring/scenes"),
  start: () => cvApiClient.post<CVMonitoringStatus>("/v1/monitoring/start"),
  stop: () => cvApiClient.post<CVMonitoringStatus>("/v1/monitoring/stop"),
  beginMarkup: () => cvApiClient.post<CVMonitoringStatus>("/v1/monitoring/markup/begin"),
  finishMarkup: () => cvApiClient.post<CVMonitoringStatus>("/v1/monitoring/markup/finish"),
};

export const cvMarkupApi = {
  getFrameUrl: (cameraId: number) => `/cv/v1/markup/cameras/${cameraId}/frame`,
  buildScene: (body: {
    camera_id: number;
    image_width: number;
    image_height: number;
    containers: MarkupContainerPayload[];
  }) => cvApiClient.post<MarkupSceneResponse>("/v1/markup/scene", body),
  save: (body: {
    camera_id: number;
    containers: MarkupContainerPayload[];
    replace_existing?: boolean;
  }) => cvApiClient.post<{ mode: "idle"; camera_id: number; saved: ParkingSceneContainer[]; count: number }>(
    "/v1/markup/save",
    body
  ),
};
