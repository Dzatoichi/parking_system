import React, { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Filter, MapPin, Play, RefreshCw, Square, X } from "lucide-react";

import {
  cvMonitoringApi,
  type SpotRead,
  type SpotStatus,
} from "../services/pmApi";
import { getApiErrorMessage } from "../lib/api";
import { useParkingMapData } from "../hooks/useParkingMapData";
import { ParkingSceneWidget } from "./ParkingSceneWidget";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

type SpotFilter = "all" | SpotStatus | "disabled";

const STATUS_LABELS: Record<SpotStatus, string> = {
  free: "свободно",
  occupied: "занято",
  reserved: "забронировано",
};

const SPOT_FILL: Record<SpotStatus, string> = {
  free: "#bbf7d0",
  occupied: "#fecaca",
  reserved: "#fef08a",
};

const SPOT_STROKE: Record<SpotStatus, string> = {
  free: "#16a34a",
  occupied: "#dc2626",
  reserved: "#ca8a04",
};

function toPolygonPoints(points: number[][]): string {
  return points.map(([x, y]) => `${x},${y}`).join(" ");
}

function statusClass(status?: string) {
  if (status === "monitoring") return "text-green-700 bg-green-50 border-green-200";
  if (status === "markup") return "text-yellow-700 bg-yellow-50 border-yellow-200";
  return "text-gray-700 bg-gray-50 border-gray-200";
}

export function ParkingMap() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<SpotFilter>("all");
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [selectedParkingId, setSelectedParkingId] = useState<number | null>(null);
  const [selectedSpot, setSelectedSpot] = useState<SpotRead | null>(null);
  const [monitorActionError, setMonitorActionError] = useState<string | null>(null);

  const { error, loading, parking, parkings, refetch, spots } = useParkingMapData(selectedParkingId);

  const monitoringQuery = useQuery({
    queryKey: ["cvMonitoringStatus"],
    queryFn: () => cvMonitoringApi.getStatus(),
    refetchInterval: 2_000,
    retry: false,
  });

  const monitoring = monitoringQuery.data?.data;
  const refreshMonitoring = () => {
    setMonitorActionError(null);
    return queryClient.invalidateQueries({ queryKey: ["cvMonitoringStatus"] });
  };
  const showMonitorError = (err: unknown) => {
    setMonitorActionError(getApiErrorMessage(err, "Не удалось выполнить команду мониторинга"));
  };

  const startMonitoring = useMutation({
    mutationFn: () => cvMonitoringApi.start(),
    onSuccess: refreshMonitoring,
    onError: showMonitorError,
  });
  const stopMonitoring = useMutation({
    mutationFn: () => cvMonitoringApi.stop(),
    onSuccess: refreshMonitoring,
    onError: showMonitorError,
  });

  const handleRefresh = async () => {
    await refetch();
    await refreshMonitoring();
    setLastRefresh(new Date());
  };

  const filteredSpots = useMemo(
    () =>
      spots.filter((spot) => {
        if (filter === "all") return true;
        if (filter === "disabled") return spot.spot_type === "disabled";
        return spot.spot_status === filter;
      }),
    [filter, spots],
  );

  const occupiedCount = spots.filter((s) => s.spot_status === "occupied").length;
  const reservedCount = spots.filter((s) => s.spot_status === "reserved").length;
  const freeCount = spots.filter((s) => s.spot_status === "free").length;
  const busy = startMonitoring.isPending || stopMonitoring.isPending;
  const monitorError = monitorActionError || getApiErrorMessage(monitoringQuery.error, "");

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Карта парковки</h1>
          <p className="text-sm text-gray-600 mt-1">
            {parking ? `${parking.name}, ${parking.address}` : "Визуализация мест в реальном времени"}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={String(parking?.id ?? "")}
            onValueChange={(value) => {
              setSelectedParkingId(Number(value));
              setSelectedSpot(null);
            }}
          >
            <SelectTrigger className="w-64">
              <SelectValue placeholder="Парковка" />
            </SelectTrigger>
            <SelectContent>
              {parkings.map((item) => (
                <SelectItem key={item.id} value={String(item.id)}>
                  {item.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          <Select value={filter} onValueChange={(v) => setFilter(v as SpotFilter)}>
            <SelectTrigger className="w-48">
              <Filter className="w-4 h-4 mr-2" />
              <SelectValue placeholder="Фильтр мест" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Все места</SelectItem>
              <SelectItem value="free">Только свободные</SelectItem>
              <SelectItem value="occupied">Только занятые</SelectItem>
              <SelectItem value="reserved">Только бронь</SelectItem>
              <SelectItem value="disabled">Для инвалидов</SelectItem>
            </SelectContent>
          </Select>

          {/* <Button onClick={handleRefresh} variant="outline" className="gap-2">
            <RefreshCw className="w-4 h-4" />
            Обновить
          </Button> */}
        </div>
      </div>

      <Card className="p-4 bg-white shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className={`px-3 py-1.5 rounded-md border text-sm font-medium ${statusClass(monitoring?.mode)}`}>
              CV: {monitoringQuery.isLoading ? "проверка" : monitoring?.mode ?? "offline"}
            </span>
            <span className="text-sm text-gray-600">
              Камер: {monitoring?.monitor?.cameras ?? 0}, процессоров: {monitoring?.monitor?.active_processors ?? 0}
            </span>
            <span className="text-sm text-gray-600">
              Кадров: {monitoring?.monitor?.stats?.total_frames_processed ?? 0}
            </span>
          </div>
          <div className="flex items-center gap-2">
            <Button
              onClick={() => startMonitoring.mutate()}
              disabled={busy || monitoring?.running || monitoring?.mode === "markup"}
              className="gap-2 bg-green-600 hover:bg-green-700"
            >
              <Play className="w-4 h-4" />
              Старт
            </Button>
            <Button
              onClick={() => stopMonitoring.mutate()}
              disabled={busy || !monitoring?.running}
              variant="outline"
              className="gap-2"
            >
              <Square className="w-4 h-4" />
              Стоп
            </Button>
          </div>
        </div>
        {monitorError && <p className="text-sm text-red-600 mt-3">{monitorError}</p>}
      </Card>

      {loading && <p className="text-sm text-gray-500">Загрузка данных...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      <ParkingSceneWidget />

      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] gap-5">
        <div className="space-y-4">
          <Card className="p-4 bg-white shadow-sm">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-lg font-semibold text-gray-900">Схема мест</h3>
              <p className="text-sm text-gray-500">
                Обновлено: {lastRefresh.toLocaleTimeString("ru-RU")}
              </p>
            </div>

            <div className="overflow-auto rounded-md border border-gray-100 bg-gray-50">
              <svg viewBox="0 0 1000 800" width="100%" style={{ minHeight: 440, display: "block" }}>
                <rect x="60" y="70" width="880" height="660" rx="8" fill="#f8fafc" stroke="#e5e7eb" />
                <text x="740" y="120" textAnchor="middle" fontSize="14" fill="#64748b">
                  тестовая камера Сергея
                </text>
                <line x1="520" y1="120" x2="520" y2="660" stroke="#cbd5e1" strokeWidth="4" strokeDasharray="12 12" />

                {filteredSpots.map((spot) => {
                  const coords = spot.spot_coordinates;
                  if (!coords?.points?.length) return null;

                  const isDisabled = spot.spot_type === "disabled";
                  const fill = SPOT_FILL[spot.spot_status] ?? "#e5e7eb";
                  const stroke = isDisabled ? "#2563eb" : (SPOT_STROKE[spot.spot_status] ?? "#9ca3af");
                  const isSelected = selectedSpot?.id === spot.id;

                  return (
                    <g
                      key={spot.id}
                      style={{ cursor: "pointer" }}
                      onClick={() => setSelectedSpot(isSelected ? null : spot)}
                    >
                      <polygon
                        points={toPolygonPoints(coords.points)}
                        fill={fill}
                        stroke={isSelected ? "#2563eb" : stroke}
                        strokeWidth={isSelected ? 4 : 2}
                        opacity={0.95}
                      />
                      <text
                        x={coords.center_x}
                        y={coords.center_y - 10}
                        textAnchor="middle"
                        dominantBaseline="central"
                        fontSize={18}
                        fontWeight={700}
                        fill="#111827"
                        pointerEvents="none"
                      >
                        {spot.spot_number}
                      </text>
                      <text
                        x={coords.center_x}
                        y={coords.center_y + 18}
                        textAnchor="middle"
                        dominantBaseline="central"
                        fontSize={14}
                        fill="#374151"
                        pointerEvents="none"
                      >
                        {STATUS_LABELS[spot.spot_status]}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          </Card>

          {selectedSpot && (
            <Card className="p-4 bg-white shadow-sm border-l-4 border-blue-600">
              <div className="flex items-start justify-between gap-4">
                <div className="space-y-1">
                  <p className="font-semibold text-gray-900">Место {selectedSpot.spot_number}</p>
                  <p className="text-sm text-gray-600">
                    Статус: <span className="font-medium">{STATUS_LABELS[selectedSpot.spot_status]}</span>
                  </p>
                  <p className="text-sm text-gray-600">
                    ID места: {selectedSpot.id}
                  </p>
                  {selectedSpot.current_vehicle_id && (
                    <p className="text-sm text-gray-600">
                      ТС: #{selectedSpot.current_vehicle_id}
                    </p>
                  )}
                </div>
                <button onClick={() => setSelectedSpot(null)} className="text-gray-400 hover:text-gray-700">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </Card>
          )}
        </div>

        <div className="space-y-4">
          <Card className="p-5 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Статистика</h3>
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Всего мест</span>
                <span className="font-semibold">{spots.length}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Свободно</span>
                <span className="font-semibold text-green-700">{freeCount}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Занято</span>
                <span className="font-semibold text-red-700">{occupiedCount}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Бронь</span>
                <span className="font-semibold text-yellow-700">{reservedCount}</span>
              </div>
              <div className="border-t border-gray-100 pt-3 flex justify-between text-sm">
                <span className="text-gray-600">Заполненность</span>
                <span className="font-semibold">
                  {spots.length ? `${Math.round(((occupiedCount + reservedCount) / spots.length) * 100)}%` : "-"}
                </span>
              </div>
            </div>
          </Card>

          <Card className="p-5 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Места</h3>
            <div className="space-y-2">
              {spots.map((spot) => (
                <button
                  key={spot.id}
                  onClick={() => setSelectedSpot(spot)}
                  className="w-full flex items-center justify-between rounded-md border border-gray-100 px-3 py-2 text-left hover:bg-gray-50"
                >
                  <span className="flex items-center gap-2">
                    <MapPin className="w-4 h-4 text-gray-400" />
                    <span className="text-sm font-medium text-gray-900">{spot.spot_number}</span>
                  </span>
                  <span className={`text-xs font-medium ${
                    spot.spot_status === "occupied"
                      ? "text-red-700"
                      : spot.spot_status === "reserved"
                        ? "text-yellow-700"
                        : "text-green-700"
                  }`}>
                    {STATUS_LABELS[spot.spot_status]}
                  </span>
                </button>
              ))}
              {spots.length === 0 && <p className="text-sm text-gray-400">Нет мест для выбранной парковки</p>}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
