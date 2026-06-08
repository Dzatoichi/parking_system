import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getApiErrorMessage } from "../lib/api";
import { parkingApi, spotApi, type ParkingRead, type SpotRead } from "../services/pmApi";

const NO_ACTIVE_PARKING_MESSAGE = "Нет активных парковок. Добавьте данные в БД.";
const SERGEY_TEST_PARKING_NAME = "Парковка Сергея 5005";

export function useParkingMapData(selectedParkingId?: number | null) {
  const [wsSpots, setWsSpots] = useState<SpotRead[] | null>(null);
  const [wsError, setWsError] = useState<string | null>(null);
  const lastWsMessageRef = useRef<string>("");

  const parkingsQuery = useQuery({
    queryKey: ["parkingMapParkings"],
    queryFn: () => parkingApi.getAll({ only_active: true, page: 1, size: 200 }),
    retry: false,
  });

  const parkings: ParkingRead[] = parkingsQuery.data?.data.items ?? [];
  const sergeyParking = parkings.find((parking) => parking.name === SERGEY_TEST_PARKING_NAME);
  const parking =
    parkings.find((item) => item.id === selectedParkingId) ??
    sergeyParking ??
    parkings[0] ??
    null;
  const parkingId = parking?.id ?? null;

  const spotsQuery = useQuery<SpotRead[]>({
    queryKey: ["parkingMapSpots", parkingId],
    queryFn: async () => {
      const response = await spotApi.getMap(parkingId as number);
      return response.data;
    },
    enabled: parkingId != null,
    retry: false,
  });

  useEffect(() => {
    setWsSpots(null);
    setWsError(null);

    if (parkingId == null) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/spots/${parkingId}/map/ws`);

    ws.onmessage = (event) => {
      try {
        if (event.data === lastWsMessageRef.current) return;
        lastWsMessageRef.current = event.data;

        const payload = JSON.parse(event.data) as { type?: string; data?: SpotRead[] };
        if (payload.type === "spots_map" && Array.isArray(payload.data)) {
          setWsSpots(payload.data);
          setWsError(null);
        }
      } catch {
        setWsError("Ошибка потока схемы парковки");
      }
    };

    ws.onerror = () => {
      setWsError("WebSocket схемы парковки недоступен");
    };

    return () => {
      ws.close();
    };
  }, [parkingId]);

  const spots = wsSpots ?? spotsQuery.data ?? [];

  return {
    error:
      parkingsQuery.isSuccess && parking === null
        ? NO_ACTIVE_PARKING_MESSAGE
        : wsError || getApiErrorMessage(spotsQuery.error ?? parkingsQuery.error, "Ошибка загрузки данных"),
    loading:
      parkingsQuery.isLoading ||
      parkingsQuery.isFetching ||
      (spots.length === 0 && (spotsQuery.isLoading || spotsQuery.isFetching)),
    parking,
    parkings,
    refetch: async () => {
      await Promise.all([parkingsQuery.refetch(), spotsQuery.refetch()]);
    },
    spots,
  };
}
