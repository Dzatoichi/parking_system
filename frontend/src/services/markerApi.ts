import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_MARKER_API_URL ||
  (import.meta.env.PROD ? '/marker-api' : 'http://localhost:8002');

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('Marker API Error:', error.message);
    return Promise.reject(error);
  }
);

export const markerAPI = {
  uploadImage: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    return api.post('/api/upload_image', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  addContainer: () => api.post('/api/add_container'),
  addPoint: (x: number, y: number) => api.post('/api/add_point', { x, y }),
  createContainer: (length: number, width: number, height: number) =>
    api.post('/api/create_container', { length, width, height }),
  addCarBbox: (x1: number, y1: number, x2: number, y2: number, containerIndex: number) =>
    api.post('/api/add_car_bbox', { x1, y1, x2, y2, container_index: containerIndex }),
  createShadow: (carBbox: { x1: number; y1: number; x2: number; y2: number }, carDimensions: object, containerIndex: number) =>
    api.post('/api/create_shadow', {
      car_bbox: { ...carBbox, container_index: containerIndex },
      car_dimensions: carDimensions,
      container_index: containerIndex,
    }),
  getState: () => api.get('/api/get_state'),
  getImage: () => api.get('/api/get_image'),
  setActiveContainer: (containerIndex: number) =>
    api.post('/api/set_active_container', null, { params: { container_index: containerIndex } }),
  clearAll: () => api.post('/api/clear_all'),
  clearCars: () => api.post('/api/clear_cars'),
};

export default api;
