import React, { useMemo, useState } from "react";
import { Accessibility, RefreshCw, Filter, MapPin } from "lucide-react";

import { useParkingMapData } from "../hooks/useParkingMapData";
import type { SpotReadShort, SpotStatus } from "../services/pmApi";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

type SpotFilter = "all" | SpotStatus | "disabled";

const STATUS_LABELS: Record<SpotStatus, string> = {
  free: "свободно",
  occupied: "занято",
  reserved: "забронировано",
};

const getStatusLabel = (status: SpotStatus) => STATUS_LABELS[status] ?? status;

export function ParkingMap() {
  const [filter, setFilter] = useState<SpotFilter>("all");
  const [lastRefresh, setLastRefresh] = useState(new Date());
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

  const getSpotColor = (spot: SpotReadShort) => {
    if (spot.spot_type === "disabled") {
      switch (spot.spot_status) {
        case "free":
          return "bg-blue-50 border-blue-300 text-blue-800";
        case "occupied":
          return "bg-red-100 border-blue-400 text-red-800";
        case "reserved":
          return "bg-yellow-50 border-blue-400 text-yellow-800";
        default:
          return "bg-gray-100 border-blue-300 text-gray-800";
      }
    }

    switch (spot.spot_status) {
      case "free":
        return "bg-green-100 border-green-300 text-green-800";
      case "occupied":
        return "bg-red-100 border-red-300 text-red-800";
      case "reserved":
        return "bg-yellow-50 border-yellow-300 text-yellow-800";
      default:
        return "bg-gray-100 border-gray-300 text-gray-800";
    }
  };

  const getSpotIcon = (status: SpotStatus) => {
    switch (status) {
      case "free":
        return <div className="text-lg">⬜</div>;
      case "occupied":
        return <div className="text-2xl mb-1">🚗</div>;
      case "reserved":
        return <div className="text-2xl mb-1">⏱</div>;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 mb-2">Карта парковки</h1>
          <p className="text-gray-600">
            {parking
              ? `${parking.name}, ${parking.address}`
              : "Визуализация парковки в реальном времени"}
          </p>
        </div>

        <div className="flex items-center space-x-4">
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-40">
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
        <div className="col-span-3">
          <Card className="p-6 bg-white shadow-sm">
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Схема парковки</h3>
              <p className="text-sm text-gray-600">
                Обновлено: {lastRefresh.toLocaleTimeString("ru-RU")}
              </p>
            </div>

            <div className="grid grid-cols-4 gap-4">
              {filteredSpots.map((spot) => (
                <div
                  key={spot.id}
                  className={`aspect-square rounded-lg border-2 p-4 flex flex-col items-center justify-center relative transition-all duration-200 hover:scale-105 cursor-pointer ${getSpotColor(spot)}`}
                  title={`Место ${spot.spot_number} - ${getStatusLabel(spot.spot_status)}${
                    spot.spot_type === "disabled" ? ", для инвалидов" : ""
                  }`}
                >
                  {spot.spot_type === "disabled" && (
                    <div className="absolute left-2 top-2 rounded-full bg-blue-600 p-1 text-white">
                      <Accessibility className="h-3.5 w-3.5" aria-label="Место для инвалидов" />
                    </div>
                  )}
                  <div className="text-sm font-semibold mb-2">{spot.spot_number}</div>

                  {getSpotIcon(spot.spot_status)}

                  {spot.spot_status === "occupied" && (
                    <div className="text-xs font-medium">ID {spot.current_vehicle_id ?? "-"}</div>
                  )}
                  <div className="mt-1 text-center text-[11px] font-medium leading-tight">
                    {getStatusLabel(spot.spot_status)}
                  </div>
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Обозначения</h3>
            <div className="space-y-3">
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 bg-green-500 rounded" />
                <span className="text-sm">
                  Свободно ({spots.filter((s) => s.spot_status === "free").length} мест)
                </span>
              </div>
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 bg-red-500 rounded" />
                <span className="text-sm">
                  Занято ({spots.filter((s) => s.spot_status === "occupied").length} мест)
                </span>
              </div>
              <div className="flex items-center space-x-3">
                <div className="flex h-4 w-4 items-center justify-center rounded bg-blue-600 text-white">
                  <Accessibility className="h-3 w-3" />
                </div>
                <span className="text-sm">
                  Для инвалидов ({disabledSpots.length} мест)
                </span>
              </div>
            </div>
          </Card>

          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Статистика</h3>
            <div className="space-y-4">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Заполненность</span>
                <span className="text-sm font-semibold">
                  {spots.length
                    ? `${Math.round((spots.filter((s) => s.spot_status === "occupied").length / spots.length) * 100)}%`
                    : "-"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Пик загрузки</span>
                <span className="text-sm font-semibold">9:00 - 17:00</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Ср. время</span>
                <span className="text-sm font-semibold">2.5 часа</span>
              </div>
              <div className="border-t border-gray-100 pt-4">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-sm text-gray-600">Места для инвалидов</span>
                  <span className="text-sm font-semibold">{disabledSpots.length}</span>
                </div>
                <div className="space-y-1 text-xs text-gray-600">
                  <div className="flex justify-between">
                    <span>Свободно</span>
                    <span>{disabledSpots.filter((s) => s.spot_status === "free").length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Занято</span>
                    <span>{disabledSpots.filter((s) => s.spot_status === "occupied").length}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Бронь</span>
                    <span>{disabledSpots.filter((s) => s.spot_status === "reserved").length}</span>
                  </div>
                </div>
              </div>
            </div>
          </Card>

          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Активные ТС</h3>
            <div className="space-y-3">
              {spots
                .filter((spot) => spot.spot_status === "occupied")
                .slice(0, 5)
                .map((spot) => (
                  <div
                    key={spot.id}
                    className="flex items-center justify-between py-2 border-b border-gray-100 last:border-b-0"
                  >
                    <div className="flex items-center space-x-2">
                      <MapPin className="w-4 h-4 text-gray-400" />
                      <div>
                        <p className="text-sm font-medium">ТС #{spot.current_vehicle_id ?? "-"}</p>
                        <p className="text-xs text-gray-600">Место {spot.spot_number}</p>
                      </div>
                    </div>
                    <span className="text-xs text-gray-500">занято</span>
                  </div>
                ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
