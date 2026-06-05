import { useQuery } from "@tanstack/react-query";

import { getApiErrorMessage } from "../lib/api";
import { parkingApi, spotApi, type ParkingRead, type SpotRead } from "../services/pmApi";

const NO_ACTIVE_PARKING_MESSAGE =
  "Нет активных парковок. Добавьте данные в БД.";

const SERGEY_TEST_PARKING_NAME = "Парковка Сергея 5005";
const SPOTS_POLL_INTERVAL_MS = 1_000;

export function useParkingMapData(selectedParkingId?: number | null) {
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
    refetchInterval: SPOTS_POLL_INTERVAL_MS,
    retry: false,
  });

  return {
    error:
      parkingsQuery.isSuccess && parking === null
        ? NO_ACTIVE_PARKING_MESSAGE
        : getApiErrorMessage(spotsQuery.error ?? parkingsQuery.error, "Ошибка загрузки данных"),
    loading:
      parkingsQuery.isLoading ||
      parkingsQuery.isFetching ||
      spotsQuery.isLoading ||
      spotsQuery.isFetching,
    parking,
    parkings,
    refetch: async () => {
      await Promise.all([parkingsQuery.refetch(), spotsQuery.refetch()]);
    },
    spots: spotsQuery.data ?? [],
  };
}
