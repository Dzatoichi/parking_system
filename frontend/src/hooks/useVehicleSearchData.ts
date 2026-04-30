import { useEffect, useMemo, useState } from "react";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getApiErrorMessage } from "../lib/api";
import {
  spotApi,
  vehicleApi,
  type SpotReadShort,
  type TrackingEventRead,
  type VehicleRead,
} from "../services/pmApi";
import { useActiveParking } from "./useActiveParking";

export function useVehicleSearchData() {
  const queryClient = useQueryClient();
  const activeParkingQuery = useActiveParking();
  const activeParkingId = activeParkingQuery.data?.id ?? null;
  const [selectedVehicleId, setSelectedVehicleId] = useState<number | null>(null);

  const vehiclesQuery = useQuery<VehicleRead[]>({
    queryKey: ["vehicles"],
    queryFn: async () => {
      const response = await vehicleApi.getAll({ page: 1, size: 200 });
      return response.data.items;
    },
  });

  const spotsQuery = useQuery<SpotReadShort[]>({
    queryKey: ["vehicleSearchSpots", activeParkingId],
    queryFn: async () => {
      const response = await spotApi.getByParking(activeParkingId as number, { page: 1, size: 200 });
      return response.data.items;
    },
    enabled: activeParkingId != null,
    retry: false,
  });

  const selectedVehicle = useMemo(
    () => vehiclesQuery.data?.find((vehicle) => vehicle.id === selectedVehicleId) ?? null,
    [selectedVehicleId, vehiclesQuery.data],
  );

  useEffect(() => {
    if (!vehiclesQuery.data || vehiclesQuery.data.length === 0) {
      setSelectedVehicleId(null);
      return;
    }

    const currentSelectionExists = vehiclesQuery.data.some(
      (vehicle) => vehicle.id === selectedVehicleId,
    );

    if (!currentSelectionExists) {
      setSelectedVehicleId(vehiclesQuery.data[0].id);
    }
  }, [selectedVehicleId, vehiclesQuery.data]);

  const historyQuery = useQuery<TrackingEventRead[]>({
    queryKey: ["vehicleHistory", selectedVehicleId],
    queryFn: async () => {
      const response = await vehicleApi.getHistory(selectedVehicleId as number, { limit: 100 });
      return response.data.events;
    },
    enabled: selectedVehicleId != null,
    retry: false,
  });

  const toggleBlockMutation = useMutation({
    mutationFn: async (vehicle: VehicleRead) =>
      vehicleApi.setBlockByPlate(vehicle.plate_number, !vehicle.is_blocked),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["vehicles"] });
      if (selectedVehicleId != null) {
        await queryClient.invalidateQueries({ queryKey: ["vehicleHistory", selectedVehicleId] });
      }
    },
  });

  return {
    error: getApiErrorMessage(
      vehiclesQuery.error ?? activeParkingQuery.error,
      "Ошибка загрузки транспорта",
    ),
    history: historyQuery.data ?? [],
    loading:
      vehiclesQuery.isLoading ||
      vehiclesQuery.isFetching ||
      toggleBlockMutation.isPending,
    selectedVehicle,
    selectedVehicleId,
    setSelectedVehicleId,
    spots: spotsQuery.data ?? [],
    toggleBlock: async () => {
      if (!selectedVehicle) {
        return;
      }

      await toggleBlockMutation.mutateAsync(selectedVehicle);
    },
    vehicles: vehiclesQuery.data ?? [],
  };
}
