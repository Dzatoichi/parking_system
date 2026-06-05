import Constants from "expo-constants";
import { Platform } from "react-native";
import { Booking, Parking, ParkingSpot, Payment, Vehicle } from "./types";
import { demoBooking, demoParkings, demoSpots, demoVehicles } from "./mockData";

const explicitApiUrl = process.env.EXPO_PUBLIC_API_URL;
const legacyParkingApiUrl = process.env.EXPO_PUBLIC_PARKING_API_URL;
const legacyAuthApiUrl = process.env.EXPO_PUBLIC_AUTH_API_URL;
const gatewayPort = process.env.EXPO_PUBLIC_API_PORT ?? "8080";
const demoMode = process.env.EXPO_PUBLIC_DEMO_MODE === "true";

type FastApiValidationError = {
  loc?: Array<string | number>;
  msg?: string;
  type?: string;
};

type ErrorPayload = {
  detail?: string | FastApiValidationError[] | Record<string, unknown>;
  message?: string;
  error?: string;
};

export class ApiError extends Error {
  status: number;
  code: "network" | "unauthorized" | "forbidden" | "not_found" | "validation" | "server" | "unknown";
  details?: unknown;

  constructor(status: number, message: string, code: ApiError["code"], details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

type AuthApiResponse = {
  user: { id?: number; full_name?: string | null; email?: string; role?: string };
  tokens: { access_token: string; refresh_token: string };
};

type RequestOptions = {
  token?: string | null;
  method?: "GET" | "POST" | "PATCH";
  body?: unknown;
  api?: "gateway" | "parking" | "auth";
};

export function getApiBaseUrl(api: RequestOptions["api"] = "gateway") {
  if (api === "auth" && legacyAuthApiUrl) {
    return stripTrailingSlash(legacyAuthApiUrl);
  }
  if (api === "parking" && legacyParkingApiUrl) {
    return stripTrailingSlash(legacyParkingApiUrl);
  }
  if (explicitApiUrl) {
    return stripTrailingSlash(explicitApiUrl);
  }

  const expoHost = getExpoHost();
  if (expoHost) {
    return `http://${expoHost}:${gatewayPort}`;
  }

  if (Platform.OS === "android") {
    return `http://10.0.2.2:${gatewayPort}`;
  }

  return `http://localhost:${gatewayPort}`;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = `${getApiBaseUrl(options.api)}${path}`;

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(options.token ? { Authorization: `Bearer ${options.token}` } : {})
      },
      body: options.body ? JSON.stringify(options.body) : undefined
    });
  } catch (error) {
    throw new ApiError(
      0,
      `Не удалось подключиться к API: ${getApiBaseUrl(options.api)}. Проверьте, что docker compose запущен, телефон и компьютер в одной сети, а порт ${gatewayPort} доступен.`,
      "network",
      error
    );
  }

  if (!response.ok) {
    throw await toApiError(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  if (!text) {
    return undefined as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch (error) {
    throw new ApiError(response.status, "API вернул некорректный JSON.", "unknown", error);
  }
}

async function toApiError(response: Response) {
  const payload = await readErrorPayload(response);
  const message = getPayloadMessage(payload) ?? getDefaultStatusMessage(response.status);

  if (response.status === 401) {
    return new ApiError(response.status, "Сессия истекла или токен недействителен. Войдите заново.", "unauthorized", payload);
  }
  if (response.status === 403) {
    return new ApiError(response.status, "Недостаточно прав для выполнения действия.", "forbidden", payload);
  }
  if (response.status === 404) {
    return new ApiError(response.status, message, "not_found", payload);
  }
  if (response.status === 422) {
    return new ApiError(response.status, message, "validation", payload);
  }
  if (response.status >= 500) {
    return new ApiError(response.status, "Сервер временно недоступен или вернул ошибку. Попробуйте позже.", "server", payload);
  }

  return new ApiError(response.status, message, "unknown", payload);
}

async function readErrorPayload(response: Response): Promise<ErrorPayload | string | null> {
  const text = await response.text();
  if (!text) {
    return null;
  }
  try {
    return JSON.parse(text) as ErrorPayload;
  } catch {
    return text;
  }
}

function getPayloadMessage(payload: ErrorPayload | string | null) {
  if (!payload) {
    return null;
  }
  if (typeof payload === "string") {
    return payload;
  }
  if (payload.message) {
    return payload.message;
  }
  if (payload.error) {
    return payload.error;
  }
  if (typeof payload.detail === "string") {
    return payload.detail;
  }
  if (Array.isArray(payload.detail)) {
    return payload.detail.map((item) => item.msg).filter(Boolean).join("\n");
  }
  return null;
}

function getDefaultStatusMessage(status: number) {
  if (status === 400) {
    return "Некорректный запрос.";
  }
  if (status === 409) {
    return "Действие конфликтует с текущим состоянием данных.";
  }
  return `API вернул ошибку ${status}.`;
}

function unwrapList<T>(payload: T[] | { data?: T[]; items?: T[] }): T[] {
  if (Array.isArray(payload)) {
    return payload;
  }
  return payload.data ?? payload.items ?? [];
}

function normalizeVehicle(vehicle: Vehicle): Vehicle {
  const plate = vehicle.plate_number ?? vehicle.number_plate ?? vehicle.name ?? "";
  return {
    ...vehicle,
    plate_number: plate,
    number_plate: plate,
    name: vehicle.name ?? plate
  };
}

function stripTrailingSlash(value: string) {
  return value.replace(/\/+$/, "");
}

function getExpoHost() {
  const hostUri = Constants.expoConfig?.hostUri ?? Constants.manifest2?.extra?.expoGo?.debuggerHost;
  if (!hostUri || typeof hostUri !== "string") {
    return null;
  }
  return hostUri.split(":")[0] || null;
}

export function isUnauthorizedError(error: unknown) {
  return error instanceof ApiError && error.code === "unauthorized";
}

export function getErrorMessage(error: unknown) {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Неизвестная ошибка.";
}

export async function login(email: string, password: string): Promise<AuthApiResponse> {
  if (demoMode) {
    return {
      user: { full_name: email.split("@")[0] || "Пользователь", role: "tenant" },
      tokens: { access_token: "demo-token", refresh_token: "demo-refresh" }
    };
  }

  return request<AuthApiResponse>("/auth/login", {
    method: "POST",
    body: { email, password }
  });
}

export async function register(email: string, password: string, role: "tenant" | "landlord"): Promise<AuthApiResponse> {
  if (demoMode) {
    return login(email, password);
  }

  return request<AuthApiResponse>("/auth/register", {
    method: "POST",
    body: {
      email,
      password,
      confirm_password: password,
      role
    }
  });
}

export async function refreshAuthToken(refreshToken: string): Promise<{ access_token: string; refresh_token: string }> {
  return request<{ access_token: string; refresh_token: string }>("/auth/refresh", {
    method: "POST",
    body: { refresh_token: refreshToken }
  });
}

export async function getParkings(token?: string | null): Promise<Parking[]> {
  if (demoMode) {
    return demoParkings;
  }
  return unwrapList(await request<Parking[] | { data?: Parking[]; items?: Parking[] }>("/parking?only_active=true", { token }));
}

export async function getSpots(parkingId: number, token?: string | null): Promise<ParkingSpot[]> {
  if (demoMode) {
    return demoSpots.filter((spot) => spot.parking_id === parkingId);
  }
  return unwrapList(await request<{ data?: ParkingSpot[]; items?: ParkingSpot[] }>(`/spot/parking/${parkingId}`, { token }));
}

export async function getVehicles(token?: string | null): Promise<Vehicle[]> {
  if (demoMode) {
    return demoVehicles;
  }
  return unwrapList(await request<{ data?: Vehicle[]; items?: Vehicle[] }>("/cars/me", { token }))
    .filter((vehicle) => vehicle.id !== 0)
    .map(normalizeVehicle);
}

export async function addVehicle(numberPlate: string, token?: string | null): Promise<Vehicle> {
  if (demoMode) {
    return normalizeVehicle({ id: Date.now(), plate_number: numberPlate, name: numberPlate });
  }
  const vehicle = await request<Vehicle>("/cars/add", {
    token,
    method: "POST",
    body: { plate_number: numberPlate, name: numberPlate }
  });
  return normalizeVehicle(vehicle);
}

export async function getActiveBooking(token?: string | null): Promise<Booking | null> {
  if (demoMode) {
    return null;
  }
  try {
    const booking = await request<Booking | { detail?: string }>("/booking/me", { token });
    return "id" in booking ? booking : null;
  } catch (error) {
    if (error instanceof ApiError && error.code === "not_found") {
      return null;
    }
    throw error;
  }
}

export async function createBooking(input: {
  parkingId: number;
  spotId: number;
  vehicleId?: number;
  token?: string | null;
}): Promise<Booking> {
  const start = new Date(Date.now() + 15 * 60_000);
  const end = new Date(start.getTime() + 2 * 60 * 60_000);

  if (demoMode) {
    return {
      ...demoBooking,
      id: Date.now(),
      parking_id: input.parkingId,
      parking_spot: input.spotId,
      parking_spot_id: input.spotId,
      spot_name: input.spotId.toString().padStart(3, "0")
    };
  }

  return request<Booking>("/booking/create", {
    token: input.token,
    method: "POST",
    body: {
      parking_id: input.parkingId,
      parking_spot_id: input.spotId,
      car_id: input.vehicleId,
      start_time: start.toISOString(),
      end_time: end.toISOString(),
      hourly_rate: 100,
      total_cost: 200
    }
  });
}

export async function createMockPayment(input: {
  bookingId: number;
  userId: number;
  amount: number;
  currency?: string;
  token?: string | null;
}): Promise<Payment> {
  if (demoMode) {
    const now = new Date().toISOString();
    return {
      id: Date.now(),
      booking_id: input.bookingId,
      fine_id: null,
      user_id: input.userId,
      amount: input.amount,
      currency: input.currency ?? "RUB",
      status: "pending",
      provider: "mock",
      provider_payment_id: `mock_${Date.now()}`,
      payment_url: null,
      description: "Оплата бронирования парковочного места",
      metadata: { source: "mobile" },
      created_at: now,
      updated_at: now
    };
  }

  return request<Payment>("/payments", {
    token: input.token,
    method: "POST",
    body: {
      user_id: input.userId,
      booking_id: input.bookingId,
      amount: input.amount,
      currency: input.currency ?? "RUB",
      description: "Оплата бронирования парковочного места",
      metadata: { source: "mobile", mode: "mock" }
    }
  });
}

export async function confirmMockPayment(paymentId: number, token?: string | null): Promise<Payment> {
  if (demoMode) {
    const now = new Date().toISOString();
    return {
      id: paymentId,
      booking_id: null,
      fine_id: null,
      user_id: 1,
      amount: 0,
      currency: "RUB",
      status: "succeeded",
      provider: "mock",
      provider_payment_id: `mock_${paymentId}`,
      payment_url: null,
      description: "Оплата бронирования парковочного места",
      metadata: { source: "mobile" },
      created_at: now,
      updated_at: now
    };
  }

  return request<Payment>(`/payments/${paymentId}/confirm`, { token, method: "POST" });
}

export async function confirmBookingAfterPayment(bookingId: number, token?: string | null): Promise<Booking> {
  if (demoMode) {
    return { ...demoBooking, id: bookingId, status: 2 };
  }
  return request<Booking>(`/booking/pay/${bookingId}`, { token, method: "POST" });
}

export async function cancelBooking(bookingId: number, token?: string | null) {
  if (demoMode) {
    return true;
  }
  return request(`/booking/reject/${bookingId}`, { token, method: "POST" });
}

export async function updateOwnerSpot(spotId: number, isFree: boolean, token?: string | null) {
  if (demoMode) {
    return true;
  }
  return request(`/spot/update/${spotId}`, {
    token,
    method: "PATCH",
    body: { status: isFree ? 1 : 2 }
  });
}
