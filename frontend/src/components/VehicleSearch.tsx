import React, { useMemo, useState } from "react";
import { Search, Clock, MapPin, Car, ArrowRight } from "lucide-react";

import { useVehicleSearchData } from "../hooks/useVehicleSearchData";
import type { VehicleRead } from "../services/pmApi";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Input } from "./ui/input";

export function VehicleSearch() {
  const [searchQuery, setSearchQuery] = useState("");
  const {
    error,
    history,
    loading,
    selectedVehicle,
    setSelectedVehicleId,
    spots,
    toggleBlock,
    vehicles,
  } = useVehicleSearchData();

  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return vehicles;
    return vehicles.filter((vehicle) =>
      vehicle.plate_number.toLowerCase().includes(searchQuery.toLowerCase()),
    );
  }, [searchQuery, vehicles]);

  const handleSearch = () => {
    if (searchResults.length === 1) {
      setSelectedVehicleId(searchResults[0].id);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case "На парковке":
        return "bg-green-100 text-green-800";
      case "Выехал":
        return "bg-gray-100 text-gray-800";
      default:
        return "bg-blue-100 text-blue-800";
    }
  };

  const statusLabel = (vehicle: VehicleRead) =>
    vehicle.is_inside ? "На парковке" : "Выехал";

  const currentSpot = (vehicleId: number) => {
    const found = spots.find((spot) => spot.current_vehicle_id === vehicleId);
    return found?.spot_number ?? "Н/Д";
  };

  const formatDate = (value: string | null) =>
    value ? new Date(value).toLocaleString("ru-RU") : "Н/Д";

  const getActionIcon = (action: string) => {
    switch (action) {
      case "Въезд":
        return <ArrowRight className="w-4 h-4 text-green-600 rotate-180" />;
      case "Выезд":
        return <ArrowRight className="w-4 h-4 text-red-600" />;
      case "Припаркован":
        return <Car className="w-4 h-4 text-blue-600" />;
      case "Перемещение":
        return <MapPin className="w-4 h-4 text-yellow-600" />;
      default:
        return <Clock className="w-4 h-4 text-gray-600" />;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">Поиск транспорта</h1>
        <p className="text-gray-600">
          Поиск транспортных средств и просмотр истории перемещений
        </p>
      </div>

      <Card className="p-6 bg-white shadow-sm">
        <div className="flex items-center space-x-4">
          <div className="flex-1">
            <Input
              type="text"
              placeholder="Введите номер транспорта..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              onKeyPress={(event) => event.key === "Enter" && handleSearch()}
              className="w-full"
            />
          </div>
          <Button onClick={handleSearch} className="bg-blue-600 hover:bg-blue-700">
            <Search className="w-4 h-4 mr-2" />
            Поиск
          </Button>
        </div>
        {loading && <p className="text-sm text-gray-500 mt-3">Загрузка данных...</p>}
        {error && <p className="text-sm text-red-600 mt-3">{error}</p>}

        <div className="mt-4">
          <p className="text-sm text-gray-600 mb-2">Быстрый поиск:</p>
          <div className="flex space-x-2">
            {vehicles.slice(0, 6).map((vehicle) => (
              <Button
                key={vehicle.id}
                variant="outline"
                size="sm"
                onClick={() => {
                  setSearchQuery(vehicle.plate_number);
                  setSelectedVehicleId(vehicle.id);
                }}
              >
                {vehicle.plate_number}
              </Button>
            ))}
          </div>
        </div>
      </Card>

      {searchResults.length > 0 && (
        <div className="grid grid-cols-2 gap-6">
          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Результаты поиска</h3>
            <div className="space-y-4">
              {searchResults.map((vehicle) => (
                <div
                  key={vehicle.id}
                  onClick={() => setSelectedVehicleId(vehicle.id)}
                  className={`p-4 border rounded-lg cursor-pointer transition-all duration-200 ${
                    selectedVehicle?.id === vehicle.id
                      ? "border-blue-500 bg-blue-50"
                      : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-gray-900">{vehicle.plate_number}</h4>
                    <Badge className={getStatusColor(statusLabel(vehicle))}>
                      {statusLabel(vehicle)}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
                    <div>
                      <span className="font-medium">Место:</span>
                      <span className="ml-1">{currentSpot(vehicle.id)}</span>
                    </div>
                    <div>
                      <span className="font-medium">Статус доступа:</span>
                      <span className="ml-1">
                        {vehicle.is_blocked ? "Запрещен" : "Разрешен"}
                      </span>
                    </div>
                  </div>
                  <div className="mt-2 text-sm text-gray-600">
                    <span className="font-medium">Последнее появление:</span>
                    <span className="ml-1">{formatDate(vehicle.last_seen)}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {selectedVehicle && (
            <Card className="p-6 bg-white shadow-sm">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">История перемещений</h3>
              <div className="mb-4 p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-gray-900">{selectedVehicle.plate_number}</h4>
                  <Badge className={getStatusColor(statusLabel(selectedVehicle))}>
                    {statusLabel(selectedVehicle)}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
                  <div>
                    <span className="font-medium">Текущее место:</span>
                    <span className="ml-1">{currentSpot(selectedVehicle.id)}</span>
                  </div>
                  <div>
                    <span className="font-medium">Последнее появление:</span>
                    <span className="ml-1">{formatDate(selectedVehicle.last_seen)}</span>
                  </div>
                </div>
                <div className="mt-3">
                  <Button
                    onClick={toggleBlock}
                    variant={selectedVehicle.is_blocked ? "outline" : "destructive"}
                  >
                    {selectedVehicle.is_blocked
                      ? "Разрешить доступ"
                      : "Запретить доступ"}
                  </Button>
                </div>
              </div>

              <div className="space-y-4">
                {history.map((event, index) => (
                  <div key={index} className="flex items-start space-x-4">
                    <div className="flex-shrink-0 w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
                      {getActionIcon(event.action)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-gray-900">
                          {event.event_type} {event.spot_id ? `- spot #${event.spot_id}` : ""}
                        </p>
                        <span className="text-xs text-gray-500">
                          {new Date(event.timestamp).toLocaleString("ru-RU")}
                        </span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">camera #{event.camera_id}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {searchQuery.trim() && searchResults.length === 0 && (
        <Card className="p-6 bg-white shadow-sm text-center">
          <div className="py-8">
            <Search className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Транспорт не найден</h3>
            <p className="text-gray-600">
              Транспорт с номером "{searchQuery}" не найден. Проверьте номер и попробуйте снова.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
