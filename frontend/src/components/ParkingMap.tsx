import React, { useMemo, useState, useEffect } from "react";
import { Accessibility, RefreshCw, Filter, MapPin, X } from "lucide-react";

import { vehicleApi, type VehicleRead } from "../services/pmApi";

import { useParkingMapData } from "../hooks/useParkingMapData";
import type { SpotRead, SpotStatus } from "../services/pmApi";
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
  free:     "#bbf7d0",
  occupied: "#fecaca",
  reserved: "#fef08a",
};

const SPOT_STROKE: Record<SpotStatus, string> = {
  free:     "#16a34a",
  occupied: "#dc2626",
  reserved: "#ca8a04",
};

function toPolygonPoints(points: number[][]): string {
  return points.map(([x, y]) => `${x},${y}`).join(" ");
}

function VehicleInfo({ vehicleId }: { vehicleId: number }) {
  const [vehicle, setVehicle] = useState<VehicleRead | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    vehicleApi.getById(vehicleId)
      .then((r) => setVehicle(r.data))
      .catch(() => setVehicle(null))
      .finally(() => setLoading(false));
  }, [vehicleId]);

  if (loading) return <p className="text-sm text-gray-400">Загрузка...</p>;
  if (!vehicle) return <p className="text-sm text-gray-400">ТС #{vehicleId}</p>;

  return (
    <div className="space-y-0.5">
      <p className="text-sm font-medium text-gray-900">{vehicle.plate_number}</p>
      <p className="text-xs text-gray-500">ID: #{vehicle.id}</p>
      {vehicle.last_seen && (
        <p className="text-xs text-gray-500">
          Последний раз: {new Date(vehicle.last_seen).toLocaleTimeString("ru-RU")}
        </p>
      )}
      {vehicle.is_blocked && (
        <p className="text-xs text-red-600 font-medium">⚠ ТС заблокировано</p>
      )}
    </div>
  );
}

export function ParkingMap() {
  const [filter, setFilter] = useState<SpotFilter>("all");
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [selectedSpot, setSelectedSpot] = useState<SpotRead | null>(null);
  const { error, loading, parking, refetch, spots } = useParkingMapData();

  const handleRefresh = async () => {
    await refetch();
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

  const disabledSpots = useMemo(
    () => spots.filter((spot) => spot.spot_type === "disabled"),
    [spots],
  );

  return (
    <div className="space-y-6">

      {/* Заголовок и фильтры */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 mb-2">Карта парковки</h1>
          <p className="text-gray-600">
            {parking ? `${parking.name}, ${parking.address}` : "Визуализация парковки в реальном времени"}
          </p>
        </div>
        <div className="flex items-center space-x-4">
          <Select value={filter} onValueChange={(v) => setFilter(v as SpotFilter)}>
            <SelectTrigger className="w-44">
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
          <Button onClick={handleRefresh} variant="outline" className="flex items-center space-x-2">
            <RefreshCw className="w-4 h-4" />
            <span>Обновить</span>
          </Button>
        </div>
      </div>

      {loading && <p className="text-sm text-gray-500">Загрузка данных...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid grid-cols-4 gap-8">

        {/* SVG-карта */}
        <div className="col-span-3 space-y-3">
          <Card className="p-4 bg-white shadow-sm">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-gray-900">Схема парковки</h3>
              <p className="text-sm text-gray-500">
                Обновлено: {lastRefresh.toLocaleTimeString("ru-RU")}
              </p>
            </div>

            <div className="overflow-auto rounded-lg border border-gray-100 bg-gray-50">
              <svg
                viewBox="0 0 1000 800"
                width="100%"
                style={{ minHeight: 400, display: "block" }}
              >
                {filteredSpots.map((spot) => {
                  const coords = spot.spot_coordinates;
                  if (!coords?.points?.length) return null;

                  const isDisabled = spot.spot_type === "disabled";
                  const fill = SPOT_FILL[spot.spot_status] ?? "#e5e7eb";
                  const stroke = isDisabled ? "#2563eb" : (SPOT_STROKE[spot.spot_status] ?? "#9ca3af");
                  const strokeWidth = isDisabled ? 2.5 : 1.5;
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
                        stroke={isSelected ? "#6366f1" : stroke}
                        strokeWidth={isSelected ? 3 : strokeWidth}
                        opacity={0.9}
                      />
                      {/* Номер места */}
                      <text
                        x={coords.center_x}
                        y={coords.center_y - 4}
                        textAnchor="middle"
                        dominantBaseline="central"
                        fontSize={10}
                        fontWeight={600}
                        fill="#1f2937"
                        pointerEvents="none"
                      >
                        {spot.spot_number}
                      </text>
                      {/* Иконка инвалида */}
                      {isDisabled && (
                        <text
                          x={coords.center_x}
                          y={coords.center_y + 10}
                          textAnchor="middle"
                          dominantBaseline="central"
                          fontSize={10}
                          fill="#2563eb"
                          pointerEvents="none"
                        >
                          ♿
                        </text>
                      )}
                    </g>
                  );
                })}
              </svg>
            </div>
          </Card>

          {selectedSpot && (
              <Card className="p-4 bg-white shadow-sm border-l-4 border-indigo-500">
                <div className="flex items-start justify-between">
                  <div className="space-y-1">
                    <p className="font-semibold text-gray-900 text-base">
                      Место {selectedSpot.spot_number}
                    </p>
                    <p className="text-sm text-gray-600">
                      Статус:{" "}
                      <span className="font-medium">
                        {STATUS_LABELS[selectedSpot.spot_status] ?? selectedSpot.spot_status}
                      </span>
                    </p>
                    <p className="text-sm text-gray-600">
                      Тип:{" "}
                      <span className="font-medium">
                        {selectedSpot.spot_type === "disabled" ? "Для инвалидов" : "Стандартное"}
                      </span>
                    </p>

                    {/* Блок ТС */}
                    {selectedSpot.spot_status === "occupied" && (
                      <div className="mt-2 pt-2 border-t border-gray-100">
                        <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                          Транспортное средство
                        </p>
                        {selectedSpot.current_vehicle_id ? (
                          <VehicleInfo vehicleId={selectedSpot.current_vehicle_id} />
                        ) : (
                          <p className="text-sm text-gray-400">Нет данных о ТС</p>
                        )}
                      </div>
                    )}

                    {selectedSpot.spot_status === "reserved" && (
                      <p className="text-sm text-yellow-700 font-medium">⏱ Активная бронь</p>
                    )}
                  </div>
                  <button
                    onClick={() => setSelectedSpot(null)}
                    className="text-gray-400 hover:text-gray-600 ml-4"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </Card>
            )}
        </div>

        {/* Боковая панель */}
        <div className="space-y-6">

          {/* Обозначения */}
          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Обозначения</h3>
            <div className="space-y-3">
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 rounded-sm border-2 border-green-500 bg-green-100" />
                <span className="text-sm">
                  Свободно ({spots.filter((s) => s.spot_status === "free").length})
                </span>
              </div>
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 rounded-sm border-2 border-red-500 bg-red-100" />
                <span className="text-sm">
                  Занято ({spots.filter((s) => s.spot_status === "occupied").length})
                </span>
              </div>
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 rounded-sm border-2 border-yellow-500 bg-yellow-100" />
                <span className="text-sm">
                  Забронировано ({spots.filter((s) => s.spot_status === "reserved").length})
                </span>
              </div>
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 rounded-sm border-2 border-blue-600 bg-green-100" />
                <span className="text-sm">
                  Для инвалидов ({disabledSpots.length})
                </span>
              </div>
            </div>
          </Card>

          {/* Статистика */}
          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Статистика</h3>
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Всего мест</span>
                <span className="text-sm font-semibold">{spots.length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Свободно</span>
                <span className="text-sm font-semibold text-green-700">
                  {spots.filter((s) => s.spot_status === "free").length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Занято</span>
                <span className="text-sm font-semibold text-red-700">
                  {spots.filter((s) => s.spot_status === "occupied").length}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Забронировано</span>
                <span className="text-sm font-semibold text-yellow-700">
                  {spots.filter((s) => s.spot_status === "reserved").length}
                </span>
              </div>
              <div className="border-t border-gray-100 pt-3">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Заполненность</span>
                  <span className="text-sm font-semibold">
                    {spots.length
                      ? `${Math.round(
                          ((spots.filter((s) => s.spot_status === "occupied").length +
                            spots.filter((s) => s.spot_status === "reserved").length) /
                            spots.length) * 100
                        )}%`
                      : "—"}
                  </span>
                </div>
              </div>
              <div className="border-t border-gray-100 pt-3 space-y-1">
                <p className="text-xs font-medium text-gray-700 mb-2">Места для инвалидов</p>
                <div className="flex justify-between text-xs text-gray-600">
                  <span>Свободно</span>
                  <span>{disabledSpots.filter((s) => s.spot_status === "free").length}</span>
                </div>
                <div className="flex justify-between text-xs text-gray-600">
                  <span>Занято</span>
                  <span>{disabledSpots.filter((s) => s.spot_status === "occupied").length}</span>
                </div>
                <div className="flex justify-between text-xs text-gray-600">
                  <span>Бронь</span>
                  <span>{disabledSpots.filter((s) => s.spot_status === "reserved").length}</span>
                </div>
              </div>
            </div>
          </Card>

          {/* Активные ТС */}
          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Активные ТС</h3>
            <div className="space-y-3">
              {spots
                .filter((spot) => spot.spot_status === "occupied")
                .slice(0, 5)
                .map((spot) => (
                  <div
                    key={spot.id}
                    className="flex items-center justify-between py-2 border-b border-gray-100 last:border-b-0 cursor-pointer hover:bg-gray-50 rounded px-1"
                    onClick={() => setSelectedSpot(spot)}
                  >
                    <div className="flex items-center space-x-2">
                      <MapPin className="w-4 h-4 text-gray-400" />
                      <div>
                        <p className="text-sm font-medium">ТС #{spot.current_vehicle_id ?? "—"}</p>
                        <p className="text-xs text-gray-600">Место {spot.spot_number}</p>
                      </div>
                    </div>
                    <span className="text-xs text-gray-500">занято</span>
                  </div>
                ))}
              {spots.filter((s) => s.spot_status === "occupied").length === 0 && (
                <p className="text-sm text-gray-400">Нет активных ТС</p>
              )}
            </div>
          </Card>

        </div>
      </div>
    </div>
  );
}