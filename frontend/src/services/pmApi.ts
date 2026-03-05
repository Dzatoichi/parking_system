import axios from "axios";

export const pmApi = axios.create({
  baseURL: "/api",
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

export type CameraStatus = "ACTIVE" | "INACTIVE" | "ERROR";

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

export type SpotStatus = "FREE" | "OCCUPIED" | "RESERVED";
export type SpotType = "STANDARD" | "DISABLED" | "EV" | "MOTORCYCLE";

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
  getDetail: (spotId: number) => pmApi.get<SpotRead>(`/spots/detail/${spotId}`),
  create: (parkingId: number, body: { spot_number: string; spot_type?: SpotType; spot_coordinates: SpotCoordinates }) =>
    pmApi.post<SpotRead>(`/spots/${parkingId}`, body),
  updateCoordinates: (spotId: number, body: { spot_coordinates: SpotCoordinates }) =>
    pmApi.patch<SpotRead>(`/spots/${spotId}/coordinates`, body),
  delete: (spotId: number) => pmApi.delete(`/spots/${spotId}`),
};

