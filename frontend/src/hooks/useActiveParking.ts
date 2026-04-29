import { useQuery } from "@tanstack/react-query";

import { parkingApi, type ParkingRead } from "../services/pmApi";

type UseActiveParkingOptions = {
  refetchInterval?: number;
};

export function useActiveParking(options?: UseActiveParkingOptions) {
  return useQuery<ParkingRead | null>({
    queryKey: ["activeParking"],
    queryFn: async () => {
      const response = await parkingApi.getAll({ only_active: true, page: 1, size: 1 });
      return response.data.items[0] ?? null;
    },
    retry: false,
    refetchInterval: options?.refetchInterval,
  });
}
