import { useQuery } from "@tanstack/react-query";

import { getApiErrorMessage } from "../lib/api";
import { analyticsApi, type AnalyticsOverview } from "../services/pmApi";
import { useActiveParking } from "./useActiveParking";

const ANALYTICS_POLL_INTERVAL_MS = 30_000;
const NO_ACTIVE_PARKING_MESSAGE =
  "Нет активных парковок. Добавьте данные в БД.";

export function useAnalyticsOverview() {
  const parkingQuery = useActiveParking({ refetchInterval: ANALYTICS_POLL_INTERVAL_MS });
  const parkingId = parkingQuery.data?.id ?? null;

  const analyticsQuery = useQuery<AnalyticsOverview>({
    queryKey: ["analyticsOverview", parkingId],
    queryFn: async () => {
      const response = await analyticsApi.getOverview(parkingId as number);
      return response.data;
    },
    enabled: parkingId != null,
    refetchInterval: ANALYTICS_POLL_INTERVAL_MS,
  });

  return {
    analytics: analyticsQuery.data ?? null,
    error:
      parkingQuery.isSuccess && parkingQuery.data === null
        ? NO_ACTIVE_PARKING_MESSAGE
        : getApiErrorMessage(analyticsQuery.error ?? parkingQuery.error, "Ошибка загрузки аналитики"),
    loading:
      parkingQuery.isLoading ||
      parkingQuery.isFetching ||
      analyticsQuery.isLoading ||
      analyticsQuery.isFetching,
  };
}
