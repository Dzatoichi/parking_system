import axios from 'axios';

const API_BASE_URL =
  import.meta.env.VITE_AUTH_API_URL ||
  (import.meta.env.PROD ? '/auth-api' : 'http://localhost:8003');

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      console.error('Auth API Error:', {
        status: error.response.status,
        data: error.response.data,
        url: error.config.url,
      });
    } else if (error.request) {
      console.error('Auth Network Error:', error.message);
    }
    return Promise.reject(error);
  }
);

// Types
export interface User {
  id: number;
  email: string;
  full_name: string | null;
  role: 'tenant' | 'landlord' | 'operator' | 'admin';
  is_active: boolean;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface AuthResponse {
  user: User;
  tokens: AuthTokens;
}

// API
export const authAPI = {
  login: (email: string, password: string) =>
    api.post<AuthResponse>('/auth/login', { email, password }),

  register: (data: {
    email: string;
    password: string;
    confirm_password: string;
    full_name?: string;
    register_token?: string;
  }) => api.post<AuthResponse>('/auth/register', data),

  refresh: (refresh_token: string) =>
    api.post<AuthTokens>('/auth/refresh', { refresh_token }),

  logout: (refresh_token: string) =>
    api.post('/auth/logout', { refresh_token }),

  forgotPassword: (email: string) =>
    api.post('/auth/forgot-password', { email }),

  resetPassword: (token: string, new_password: string, confirm_new_password: string) =>
    api.post('/auth/reset-password', { token, new_password, confirm_new_password }),
};

export const userAPI = {
  getMe: (accessToken?: string) =>
    api.get<User>('/users/me', {
      headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : undefined,
    }),
  updateMe: (full_name: string) => api.patch<User>('/users/me', { full_name }),
};

export default api;