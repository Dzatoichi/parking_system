import { useQuery } from "@tanstack/react-query";

import { getApiErrorMessage } from "../lib/api";
import {
  analyticsApi,
  spotApi,
  type AnalyticsOverview,
  type ParkingStats,
} from "../services/pmApi";
import { useActiveParking } from "./useActiveParking";

const DASHBOARD_POLL_INTERVAL_MS = 30_000;
const NO_ACTIVE_PARKING_MESSAGE =
  "РќРµС‚ Р°РєС‚РёРІРЅС‹С… РїР°СЂРєРѕРІРѕРє. Р”РѕР±Р°РІСЊС‚Рµ РґР°РЅРЅС‹Рµ РІ Р‘Р”.";

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

  const error =
    getApiErrorMessage(
      parkingQuery.error ?? statsQuery.error ?? analyticsQuery.error,
      "РћС€РёР±РєР° Р·Р°РіСЂСѓР·РєРё РґР°РЅРЅС‹С…",
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
      analyticsQuery.isLoading ||
      analyticsQuery.isFetching,
    parking: parkingQuery.data ?? null,
    stats: statsQuery.data ?? null,
  };
}
