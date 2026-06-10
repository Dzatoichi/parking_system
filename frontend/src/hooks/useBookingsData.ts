import { useEffect, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { getApiErrorMessage } from "../lib/api";
import { parkingWsUrl } from "../lib/ws";
import { bookingApi, type BookingRead, type BookingStatus, type PaginatedResponse } from "../services/pmApi";
import { useActiveParking } from "./useActiveParking";

interface UseBookingsDataParams {
  status?: BookingStatus;
  vehiclePlate?: string;
  startDate?: string;
  endDate?: string;
  page?: number;
  size?: number;
}

interface UseBookingsDataReturn {
  data: PaginatedResponse<BookingRead> | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

const BOOKINGS_WS_RECONNECT_MS = 3_000;
const WS_CONNECT_DELAY_MS = 100;

export function useBookingsData({
  status,
  vehiclePlate,
  startDate,
  endDate,
  page = 1,
  size = 20,
}: UseBookingsDataParams): UseBookingsDataReturn {
  const queryClient = useQueryClient();
  const parkingQuery = useActiveParking();
  const parkingId = parkingQuery.data?.id ?? null;
  const reconnectTimerRef = useRef<number | null>(null);

  const bookingsQuery = useQuery<PaginatedResponse<BookingRead>>({
    queryKey: ["bookings", parkingId, status, vehiclePlate, startDate, endDate, page, size],
    queryFn: async () => {
      const response = await bookingApi.getAll({
        parking_id: parkingId ?? undefined,
        status,
        vehicle_plate: vehiclePlate,
        start_date: startDate,
        end_date: endDate,
        page,
        size,
      });
      return response.data;
    },
    enabled: parkingId != null,
  });

  useEffect(() => {
    if (parkingId == null) return undefined;

    let closedByEffect = false;
    let connectedOnce = false;
    let ws: WebSocket | null = null;

    const connect = () => {
      ws = new WebSocket(parkingWsUrl("/bookings/ws"));

      ws.onopen = () => {
        connectedOnce = true;
      };

      ws.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data) as { type?: string; parking_id?: number };
          if (payload.type !== "booking_changed") return;
          if (payload.parking_id !== parkingId) return;

          void queryClient.invalidateQueries({ queryKey: ["bookings", parkingId] });
        } catch {
          return;
        }
      };

      ws.onerror = () => undefined;

      ws.onclose = () => {
        if (closedByEffect) return;
        if (!connectedOnce) return;
        reconnectTimerRef.current = window.setTimeout(connect, BOOKINGS_WS_RECONNECT_MS);
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
