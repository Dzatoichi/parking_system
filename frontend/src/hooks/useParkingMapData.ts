import { useQuery } from "@tanstack/react-query";

import { getApiErrorMessage } from "../lib/api";
import { spotApi, type SpotRead } from "../services/pmApi";
import { useActiveParking } from "./useActiveParking";

const NO_ACTIVE_PARKING_MESSAGE =
  "Нет активных парковок. Добавьте данные в БД.";

const SPOTS_POLL_INTERVAL_MS = 1_000

// function normalizeSpots(spots: SpotReadShort[]) {
//   return spots.map((spot) =>
//     spot.spot_status === "reserved" ? { ...spot, spot_status: "occupied" as const } : spot,
//   );
// }

export function useParkingMapData() {
  const parkingQuery = useActiveParking();
  const parkingId = parkingQuery.data?.id ?? null;

  const spotsQuery = useQuery<SpotRead[]>({
    queryKey: ["parkingMapSpots", parkingId],
    queryFn: async () => {
      // const response = await spotApi.getMap(parkingId as number, { page: 1, size: 200 });
      const response = await spotApi.getMap(parkingId as number);
      // return normalizeSpots(response.data.items);
      // return response.data.items
      return response.data
    },
    enabled: parkingId != null,
    refetchInterval: SPOTS_POLL_INTERVAL_MS,
    retry: false,
  });

  return {
    error:
      parkingQuery.isSuccess && parkingQuery.data === null
        ? NO_ACTIVE_PARKING_MESSAGE
        : getApiErrorMessage(spotsQuery.error ?? parkingQuery.error, "Ошибка загрузки данных"),
    loading:
      parkingQuery.isLoading ||
      parkingQuery.isFetching ||
      spotsQuery.isLoading ||
      spotsQuery.isFetching,
    parking: parkingQuery.data ?? null,
    refetch: async () => {
      await Promise.all([parkingQuery.refetch(), spotsQuery.refetch()]);
    },
    spots: spotsQuery.data ?? [],
  };
}
