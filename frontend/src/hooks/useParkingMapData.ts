import { useQuery } from "@tanstack/react-query";

import { getApiErrorMessage } from "../lib/api";
import { spotApi, type SpotReadShort } from "../services/pmApi";
import { useActiveParking } from "./useActiveParking";

const NO_ACTIVE_PARKING_MESSAGE =
  "РќРµС‚ Р°РєС‚РёРІРЅС‹С… РїР°СЂРєРѕРІРѕРє. Р”РѕР±Р°РІСЊС‚Рµ РґР°РЅРЅС‹Рµ РІ Р‘Р”.";

function normalizeSpots(spots: SpotReadShort[]) {
  return spots.map((spot) =>
    spot.spot_status === "reserved" ? { ...spot, spot_status: "occupied" as const } : spot,
  );
}

export function useParkingMapData() {
  const parkingQuery = useActiveParking();
  const parkingId = parkingQuery.data?.id ?? null;

  const spotsQuery = useQuery<SpotReadShort[]>({
    queryKey: ["parkingMapSpots", parkingId],
    queryFn: async () => {
      const response = await spotApi.getByParking(parkingId as number, { page: 1, size: 200 });
      return normalizeSpots(response.data.items);
    },
    enabled: parkingId != null,
    retry: false,
  });

  return {
    error:
      parkingQuery.isSuccess && parkingQuery.data === null
        ? NO_ACTIVE_PARKING_MESSAGE
        : getApiErrorMessage(spotsQuery.error ?? parkingQuery.error, "РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё РґР°РЅРЅС‹С…"),
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
