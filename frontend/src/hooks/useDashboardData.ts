import { useQuery } from "@tanstack/react-query";

import { getApiErrorMessage } from "../lib/api";
import {
  analyticsApi,
  bookingApi,
  spotApi,
  type AnalyticsOverview,
  type PaginatedResponse,
  type BookingRead,
  type ParkingStats,
} from "../services/pmApi";
import { useActiveParking } from "./useActiveParking";

const DASHBOARD_POLL_INTERVAL_MS = 30_000;
const NO_ACTIVE_PARKING_MESSAGE =
  "Нет активных парковок. Добавьте данные в БД.";

export function useDashboardData() {
  const parkingQuery = useActiveParking({ refetchInterval: DASHBOARD_POLL_INTERVAL_MS });
  const parkingId = parkingQuery.data?.id ?? null;

  const statsQuery = useQuery<ParkingStats>({
    queryKey: ["parkingStats", parkingId],
    queryFn: async () => {
      const response = await spotApi.getStats(parkingId as number);
      return response.data;
    },
    enabled: parkingId != null,
    refetchInterval: DASHBOARD_POLL_INTERVAL_MS,
  });

  const analyticsQuery = useQuery<AnalyticsOverview>({
    queryKey: ["parkingAnalyticsOverview", parkingId],
    queryFn: async () => {
      const response = await analyticsApi.getOverview(parkingId as number);
      return response.data;
    },
    enabled: parkingId != null,
    refetchInterval: DASHBOARD_POLL_INTERVAL_MS,
  });

  const bookingsQuery = useQuery<PaginatedResponse<BookingRead>>({
    queryKey: ["dashboardBookings", parkingId],
    queryFn: async () => {
      const response = await bookingApi.getAll({ parking_id: parkingId as number, page: 1, size: 1 });
      return response.data;
    },
    enabled: parkingId != null,
    refetchInterval: DASHBOARD_POLL_INTERVAL_MS,
  });

  const error =
    getApiErrorMessage(
      parkingQuery.error ?? statsQuery.error ?? analyticsQuery.error ?? bookingsQuery.error,
      "Ошибка загрузки данных",
    ) ??
    null;

  return {
    analytics: analyticsQuery.data ?? null,
    error: parkingQuery.isSuccess && parkingQuery.data === null ? NO_ACTIVE_PARKING_MESSAGE : error,
    loading:
      parkingQuery.isLoading ||
      parkingQuery.isFetching ||
      statsQuery.isLoading ||
      statsQuery.isFetching ||
      bookingsQuery.isLoading ||
      bookingsQuery.isFetching ||
      analyticsQuery.isLoading ||
      analyticsQuery.isFetching,
    bookingsTotal: bookingsQuery.data?.total ?? 0,
    parking: parkingQuery.data ?? null,
    stats: statsQuery.data ?? null,
  };
}
