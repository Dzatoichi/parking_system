import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_CAMERAS_API_URL ||
  (import.meta.env.PROD ? '/cameras-api' : 'http://localhost:8001/api');

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      console.error('Cameras API Error:', {
        status: error.response.status,
        data: error.response.data,
        url: error.config.url,
      });
    } else if (error.request) {
      console.error('Cameras Network Error:', error.message);
    }
    return Promise.reject(error);
  }
);

export interface SegmentsConfig {
  id: number;
  name: string;
  horizontal_segments: number;
  vertical_segments: number;
  description?: string;
  created_at: string;
}

export interface Camera {
  id: number;
  video_path: string;
  clear_image_path: string;
  segments_config_id: number;
}

export interface Connection {
  id: number;
  source_camera_id: number;
  source_segment: string;
  target_camera_id: number;
  target_segment: string;
  bidirectional: boolean;
}

export const segmentsConfigAPI = {
  getAll: () => api.get<{ data: SegmentsConfig[] }>('/segments-configs'),
  getById: (id: number) => api.get<SegmentsConfig>(`/segments-configs/${id}`),
  create: (data: Omit<SegmentsConfig, 'id' | 'created_at'>) =>
    api.post<SegmentsConfig>('/segments-configs', data),
  update: (id: number, data: Partial<SegmentsConfig>) =>
    api.put<SegmentsConfig>(`/segments-configs/${id}`, data),
  delete: (id: number) => api.delete(`/segments-configs/${id}`),
};

export const camerasAPI = {
  getAll: () => api.get<{ data: Camera[] }>('/cameras'),
  getById: (id: number) => api.get<Camera>(`/cameras/${id}`),
  create: (data: Omit<Camera, 'id'>) => api.post<Camera>('/cameras', data),
  update: (id: number, data: Partial<Camera>) =>
    api.put<Camera>(`/cameras/${id}`, data),
  delete: (id: number) => api.delete(`/cameras/${id}`),
  getSegments: (id: number) => api.get(`/cameras/${id}/segments`),
};

export const connectionsAPI = {
  getAll: () => api.get<{ data: Connection[] }>('/connections'),
  getCameraConnections: (id: number) => api.get(`/connections/camera/${id}`),
  create: (data: Omit<Connection, 'id'>) =>
    api.post<Connection>('/connections', data),
  delete: (id: number) => api.delete(`/connections/${id}`),
  deleteBySegment: (cameraId: number, segment: string) =>
    api.delete(`/connections/camera/${cameraId}/segment/${segment}`),
};

export const networkAPI = {
  getStats: () => api.get('/stats'),
  getInfo: () => api.get('/info'),
  healthCheck: () => api.get('/health'),
};

export default api;
