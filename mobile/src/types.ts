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
  penalty?: number;
  owner_id?: number | null;
  rental_enabled?: boolean;
  for_disabled?: boolean;
  availability_start_time?: string | null;
  availability_end_time?: string | null;
  status: number;
  spot_status?: "FREE" | "OCCUPIED" | "RESERVED" | string;
  spot_type?: "STANDARD" | "DISABLED" | string;
};

export type Vehicle = {
  id: number;
  number_plate?: string;
  plate_number?: string;
  name?: string;
  brand?: string | null;
  color?: string | null;
  photo_urls?: VehiclePhotos | null;
};

export type VehiclePhotos = {
  front?: string;
  back?: string;
  left?: string;
  right?: string;
};

export type Booking = {
  id: number;
  start_time: string;
  end_time: string;
  status: number;
  parking_id: number;
  parking_spot?: number;
  parking_spot_id?: number;
  spot_id?: number;
  spot_name?: string;
  spot_number?: string | null;
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

export type OwnerSpotReportBooking = {
  booking_id: number;
  user_id: number;
  user_name?: string | null;
  vehicle_id?: number | null;
  vehicle_plate_number?: string | null;
  status: string;
  start_time: string;
  end_time: string;
  created_at: string;
  updated_at: string;
  hourly_rate: number;
  amount: number;
  transfer_status: string;
};

export type OwnerSpotReport = {
  spot: ParkingSpot;
  bookings: OwnerSpotReportBooking[];
  transfer_count: number;
  transfer_amount: number;
  currency: string;
};

export type AuthSession = {
  accessToken: string | null;
  refreshToken: string | null;
  userId: number;
  userName: string;
  role: UserRole;
  expiresAt: number;
};
