import { useQuery } from "@tanstack/react-query";

import { getApiErrorMessage } from "../lib/api";
import { bookingApi, type BookingStatus, type BookingRead, type PaginatedResponse } from "../services/pmApi";
import { useActiveParking } from "./useActiveParking";

interface UseBookingsDataParams {
  status?: BookingStatus;
  from?: string;
  to?: string;
  page?: number;
  size?: number;
}

interface UseBookingsDataReturn {
  data: PaginatedResponse<BookingRead> | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

const BOOKINGS_POLL_INTERVAL_MS = 30_000;

export function useBookingsData({
  status,
  from,
  to,
  page = 1,
  size = 20,
}: UseBookingsDataParams): UseBookingsDataReturn {
  const parkingQuery = useActiveParking();
  const parkingId = parkingQuery.data?.id ?? null;

  const bookingsQuery = useQuery<PaginatedResponse<BookingRead>>({
    queryKey: ["bookings", parkingId, status, from, to, page, size],
    queryFn: async () => {
      const response = await bookingApi.getAll({
        parking_id: parkingId ?? undefined,
        status,
        from,
        to,
        page,
        size,
      });
      return response.data;
    },
    enabled: parkingId != null,
    refetchInterval: BOOKINGS_POLL_INTERVAL_MS,
  });

  return {
    data: bookingsQuery.data ?? null,
    loading:
      parkingQuery.isLoading ||
      parkingQuery.isFetching ||
      bookingsQuery.isLoading ||
      bookingsQuery.isFetching,
    error: getApiErrorMessage(bookingsQuery.error ?? parkingQuery.error, "Ошибка загрузки данных"),
    refetch: async () => {
      await Promise.all([parkingQuery.refetch(), bookingsQuery.refetch()]);
    },
  };
}
