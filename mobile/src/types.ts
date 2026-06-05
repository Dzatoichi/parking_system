export type UserRole = "tenant" | "landlord";

export type Parking = {
  id: number;
  name: string;
  address: string;
  capacity?: number;
  total_spots?: number;
  latitude?: number | null;
  longitude?: number | null;
};

export type ParkingSpot = {
  id: number;
  name?: string;
  spot_number?: string;
  parking_id: number;
  hourly_rate?: number;
  for_disabled?: boolean;
  status: number;
};

export type Vehicle = {
  id: number;
  number_plate?: string;
  plate_number?: string;
  name?: string;
};

export type Booking = {
  id: number;
  start_time: string;
  end_time: string;
  status: number;
  parking_id: number;
  parking_spot?: number;
  parking_spot_id?: number;
  spot_name?: string;
  hourly_rate?: number;
  total_cost?: number;
};

export type Payment = {
  id: number;
  booking_id: number | null;
  fine_id: number | null;
  user_id: number;
  amount: number;
  currency: string;
  status: "pending" | "succeeded" | "failed" | "cancelled" | "refunded" | string;
  provider: string;
  provider_payment_id: string | null;
  payment_url: string | null;
  description: string | null;
  metadata?: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
};

export type AuthSession = {
  accessToken: string | null;
  refreshToken: string | null;
  userId: number;
  userName: string;
  role: UserRole;
};
