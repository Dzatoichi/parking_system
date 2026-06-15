import Constants from "expo-constants";
import { Platform } from "react-native";
import { Booking, OwnerSpotReport, Parking, ParkingSpot, Payment, Vehicle, VehiclePhotos } from "../../types";
import { demoBooking, demoParkings, demoSpots, demoVehicles } from "../../mockData";

const explicitApiUrl = process.env.EXPO_PUBLIC_API_URL;
const legacyParkingApiUrl = process.env.EXPO_PUBLIC_PARKING_API_URL;
const legacyAuthApiUrl = process.env.EXPO_PUBLIC_AUTH_API_URL;
const gatewayPort = process.env.EXPO_PUBLIC_API_PORT ?? "8080";
const demoMode = process.env.EXPO_PUBLIC_DEMO_MODE === "true";
const requestTimeoutMs = 10_000;

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
  const localWebApiUrl = getLocalWebApiUrl();
  if (localWebApiUrl) {
    return localWebApiUrl;
  }

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
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), requestTimeoutMs);

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      signal: controller.signal,
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
  } finally {
    clearTimeout(timeoutId);
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

function normalizeSpot(spot: ParkingSpot): ParkingSpot {
  const rawStatus = spot.status;
  const statusText = String(spot.spot_status ?? rawStatus ?? "").toLowerCase();
  const status = typeof rawStatus === "number"
    ? spot.status
    : rawStatus === true || statusText === "free" || statusText === "1"
      ? 1
      : 2;
  return {
    ...spot,
    name: spot.name ?? spot.spot_number,
    hourly_rate: spot.hourly_rate ?? 100,
    for_disabled: spot.for_disabled ?? String(spot.spot_type ?? "").toLowerCase() === "disabled",
    status
  };
}

function normalizeBooking(booking: Booking): Booking {
  const rawStatus = booking.status as unknown;
  const statusValue = typeof rawStatus === "number"
    ? rawStatus
    : ({ pending: 1, confirmed: 2, completed: 3, cancelled: 4, expired: 5 } as Record<string, number>)[String(rawStatus).toLowerCase()] ?? 1;
  return {
    ...booking,
    status: statusValue,
    parking_spot: booking.parking_spot ?? booking.parking_spot_id ?? booking.spot_id,
    parking_spot_id: booking.parking_spot_id ?? booking.parking_spot ?? booking.spot_id,
    spot_name: booking.spot_name ?? booking.spot_number ?? undefined,
    parking_id: booking.parking_id ?? 0
  };
}

function stripTrailingSlash(value: string) {
  return value.replace(/\/+$/, "");
}

function getLocalWebApiUrl() {
  if (Platform.OS !== "web" || typeof globalThis.location === "undefined") {
    return null;
  }

  const hostname = globalThis.location.hostname;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return `http://${hostname}:${gatewayPort}`;
  }

  return null;
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

export async function register(email: string, password: string): Promise<AuthApiResponse> {
  if (demoMode) {
    return login(email, password);
  }

  return request<AuthApiResponse>("/auth/register", {
    method: "POST",
    body: {
      email,
      password,
      confirm_password: password,
      role: "tenant"
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
  return unwrapList(await request<{ data?: ParkingSpot[]; items?: ParkingSpot[] }>(`/spots/${parkingId}`, { token })).map(normalizeSpot);
}

export async function getVehicles(token?: string | null): Promise<Vehicle[]> {
  if (demoMode) {
    return demoVehicles;
  }
  return unwrapList(await request<Vehicle[] | { data?: Vehicle[]; items?: Vehicle[] }>("/vehicles/me", { token })).map(normalizeVehicle);
}

export async function addVehicle(input: {
  numberPlate: string;
  brand?: string;
  color?: string;
  photos?: VehiclePhotos;
  token?: string | null;
}): Promise<Vehicle> {
  if (demoMode) {
    return normalizeVehicle({
      id: Date.now(),
      plate_number: input.numberPlate,
      name: input.numberPlate,
      brand: input.brand,
      color: input.color,
      photo_urls: input.photos
    });
  }
  const vehicle = await request<Vehicle>("/vehicles", {
    token: input.token,
    method: "POST",
    body: {
      plate_number: input.numberPlate,
      brand: input.brand,
      color: input.color,
      photo_urls: input.photos
    }
  });
  return normalizeVehicle(vehicle);
}

export async function getActiveBooking(userId: number, token?: string | null): Promise<Booking | null> {
  if (demoMode) {
    return null;
  }
  try {
    const bookings = await request<{ items?: Booking[]; data?: Booking[] }>(`/bookings/me?user_id=${userId}&size=20`, { token });
    const activeStatuses: unknown[] = [1, 2, "pending", "confirmed", "PENDING", "CONFIRMED"];
    const active = unwrapList(bookings).find((booking) => {
      const rawStatus = booking.status as unknown;
      return activeStatuses.includes(rawStatus);
    });
    return active ? normalizeBooking(active) : null;
  } catch (error) {
    if (error instanceof ApiError && error.code === "not_found") {
      return null;
    }
    throw error;
  }
}

export async function createBooking(input: {
  userId: number;
  parkingId: number;
  spotId: number;
  vehicleId?: number;
  vehiclePlate?: string;
  startTime: Date;
  endTime: Date;
  hourlyRate?: number;
  totalCost?: number;
  token?: string | null;
}): Promise<Booking> {
  const startTime = input.startTime.toISOString();
  const endTime = input.endTime.toISOString();

  if (demoMode) {
    return {
      ...demoBooking,
      id: Date.now(),
      parking_id: input.parkingId,
      parking_spot: input.spotId,
      parking_spot_id: input.spotId,
      spot_name: input.spotId.toString().padStart(3, "0"),
      start_time: startTime,
      end_time: endTime,
      hourly_rate: input.hourlyRate,
      total_cost: input.totalCost
    };
  }

  const booking = await request<Booking>("/bookings", {
    token: input.token,
    method: "POST",
    body: {
      user_id: input.userId,
      spot_id: input.spotId,
      vehicle_id: input.vehicleId,
      start_time: startTime,
      end_time: endTime
    }
  });
  return normalizeBooking({
    ...booking,
    parking_id: input.parkingId,
    hourly_rate: input.hourlyRate ?? 100,
    total_cost: input.totalCost
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
  return normalizeBooking(await request<Booking>(`/bookings/${bookingId}`, {
    token,
    method: "PATCH",
    body: { status: "confirmed" }
  }));
}

export async function cancelBooking(bookingId: number, token?: string | null) {
  if (demoMode) {
    return true;
  }
  return request(`/bookings/${bookingId}`, {
    token,
    method: "PATCH",
    body: { status: "cancelled", cancellation_reason: "mobile user rejected booking" }
  });
}

export async function getOwnerSpots(token?: string | null): Promise<ParkingSpot[]> {
  if (demoMode) {
    return demoSpots.slice(0, 4).map((spot) => ({ ...spot, owner_id: 1, rental_enabled: spot.status === 1 }));
  }
  return (await request<ParkingSpot[]>("/spots/me", { token })).map(normalizeSpot);
}

export async function registerOwnerSpot(input: {
  spotId: number;
  hourlyRate: number;
  penalty?: number;
  rentalEnabled?: boolean;
  token?: string | null;
}): Promise<ParkingSpot> {
  const spot = await request<ParkingSpot>(`/spots/${input.spotId}/ownership`, {
    token: input.token,
    method: "PATCH",
    body: {
      hourly_rate: input.hourlyRate,
      penalty: input.penalty ?? 0,
      rental_enabled: input.rentalEnabled ?? false
    }
  });
  return normalizeSpot(spot);
}

export async function updateOwnerSpot(input: {
  spotId: number;
  isFree?: boolean;
  hourlyRate?: number;
  penalty?: number;
  token?: string | null;
}): Promise<ParkingSpot> {
  if (demoMode) {
    return normalizeSpot({
      id: input.spotId,
      parking_id: 1,
      spot_number: String(input.spotId),
      status: input.isFree ? 1 : 2,
      hourly_rate: input.hourlyRate ?? 120,
      penalty: input.penalty ?? 0,
      rental_enabled: input.isFree
    });
  }
  const spot = await request<ParkingSpot>(`/spots/${input.spotId}/rental`, {
    token: input.token,
    method: "PATCH",
    body: {
      rental_enabled: input.isFree,
      hourly_rate: input.hourlyRate,
      penalty: input.penalty
    }
  });
  return normalizeSpot(spot);
}

export async function getOwnerSpotReport(spotId: number, token?: string | null): Promise<OwnerSpotReport> {
  if (demoMode) {
    return {
      spot: normalizeSpot({ id: spotId, parking_id: 1, spot_number: String(spotId), status: 1, hourly_rate: 120 }),
      bookings: [],
      transfer_count: 0,
      transfer_amount: 0,
      currency: "RUB"
    };
  }
  const report = await request<OwnerSpotReport>(`/spots/${spotId}/rental-report`, {
    token,
    method: "GET"
  });
  return { ...report, spot: normalizeSpot(report.spot) };
}
