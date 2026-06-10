import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { getApiErrorMessage } from "../lib/api";
import { parkingWsUrl } from "../lib/ws";
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
const EVENTS_WS_RECONNECT_MS = 3_000;
const WS_CONNECT_DELAY_MS = 100;
const NO_ACTIVE_PARKING_MESSAGE =
  "Нет активных парковок. Добавьте данные в БД.";

export function useDashboardData() {
  const queryClient = useQueryClient();
  const parkingQuery = useActiveParking({ refetchInterval: DASHBOARD_POLL_INTERVAL_MS });
  const parkingId = parkingQuery.data?.id ?? null;
  const reconnectTimerRef = useRef<number | null>(null);

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

  useEffect(() => {
    if (parkingId == null) return undefined;

    let closedByEffect = false;
    let connectedOnce = false;
    let ws: WebSocket | null = null;

    const refreshDashboard = () => {
      void queryClient.invalidateQueries({ queryKey: ["parkingAnalyticsOverview", parkingId] });
      void queryClient.invalidateQueries({ queryKey: ["parkingStats", parkingId] });
      void queryClient.invalidateQueries({ queryKey: ["dashboardBookings", parkingId] });
    };

    const connect = () => {
      ws = new WebSocket(parkingWsUrl("/events/ws"));

      ws.onopen = () => {
        connectedOnce = true;
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as { type?: string; parking_id?: number };
          if (payload.type !== "system_event_changed") return;
          if (payload.parking_id !== parkingId) return;

          refreshDashboard();
        } catch {
          return;
        }
      };

      ws.onerror = () => undefined;

      ws.onclose = () => {
        if (closedByEffect) return;
        if (!connectedOnce) return;
        reconnectTimerRef.current = window.setTimeout(connect, EVENTS_WS_RECONNECT_MS);
      };
    };

    reconnectTimerRef.current = window.setTimeout(connect, WS_CONNECT_DELAY_MS);

    return () => {
      closedByEffect = true;
      if (reconnectTimerRef.current != null) {
        window.clearTimeout(reconnectTimerRef.current);
      }
      if (ws?.readyState === WebSocket.OPEN || ws?.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    };
  }, [parkingId, queryClient]);

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
