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
      case "РќР° РїР°СЂРєРѕРІРєРµ":
        return "bg-green-100 text-green-800";
      case "Р’С‹РµС…Р°Р»":
        return "bg-gray-100 text-gray-800";
      default:
        return "bg-blue-100 text-blue-800";
    }
  };

  const statusLabel = (vehicle: VehicleRead) =>
    vehicle.is_inside ? "РќР° РїР°СЂРєРѕРІРєРµ" : "Р’С‹РµС…Р°Р»";

  const currentSpot = (vehicleId: number) => {
    const found = spots.find((spot) => spot.current_vehicle_id === vehicleId);
    return found?.spot_number ?? "Рќ/Р”";
  };

  const formatDate = (value: string | null) =>
    value ? new Date(value).toLocaleString("ru-RU") : "Рќ/Р”";

  const getActionIcon = (action: string) => {
    switch (action) {
      case "Р’СЉРµР·Рґ":
        return <ArrowRight className="w-4 h-4 text-green-600 rotate-180" />;
      case "Р’С‹РµР·Рґ":
        return <ArrowRight className="w-4 h-4 text-red-600" />;
      case "РџСЂРёРїР°СЂРєРѕРІР°РЅ":
        return <Car className="w-4 h-4 text-blue-600" />;
      case "РџРµСЂРµРјРµС‰РµРЅРёРµ":
        return <MapPin className="w-4 h-4 text-yellow-600" />;
      default:
        return <Clock className="w-4 h-4 text-gray-600" />;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">РџРѕРёСЃРє С‚СЂР°РЅСЃРїРѕСЂС‚Р°</h1>
        <p className="text-gray-600">
          РџРѕРёСЃРє С‚СЂР°РЅСЃРїРѕСЂС‚РЅС‹С… СЃСЂРµРґСЃС‚РІ Рё РїСЂРѕСЃРјРѕС‚СЂ РёСЃС‚РѕСЂРёРё РїРµСЂРµРјРµС‰РµРЅРёР№
        </p>
      </div>

      <Card className="p-6 bg-white shadow-sm">
        <div className="flex items-center space-x-4">
          <div className="flex-1">
            <Input
              type="text"
              placeholder="Р’РІРµРґРёС‚Рµ РЅРѕРјРµСЂ С‚СЂР°РЅСЃРїРѕСЂС‚Р°..."
              value={searchQuery}
              onChange={(event) => setSearchQuery(event.target.value)}
              onKeyPress={(event) => event.key === "Enter" && handleSearch()}
              className="w-full"
            />
          </div>
          <Button onClick={handleSearch} className="bg-blue-600 hover:bg-blue-700">
            <Search className="w-4 h-4 mr-2" />
            РџРѕРёСЃРє
          </Button>
        </div>
        {loading && <p className="text-sm text-gray-500 mt-3">Р—Р°РіСЂСѓР·РєР° РґР°РЅРЅС‹С…...</p>}
        {error && <p className="text-sm text-red-600 mt-3">{error}</p>}

        <div className="mt-4">
          <p className="text-sm text-gray-600 mb-2">Р‘С‹СЃС‚СЂС‹Р№ РїРѕРёСЃРє:</p>
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
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Р РµР·СѓР»СЊС‚Р°С‚С‹ РїРѕРёСЃРєР°</h3>
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
                      <span className="font-medium">РњРµСЃС‚Рѕ:</span>
                      <span className="ml-1">{currentSpot(vehicle.id)}</span>
                    </div>
                    <div>
                      <span className="font-medium">РЎС‚Р°С‚СѓСЃ РґРѕСЃС‚СѓРїР°:</span>
                      <span className="ml-1">
                        {vehicle.is_blocked ? "Р—Р°РїСЂРµС‰РµРЅ" : "Р Р°Р·СЂРµС€РµРЅ"}
                      </span>
                    </div>
                  </div>
                  <div className="mt-2 text-sm text-gray-600">
                    <span className="font-medium">РџРѕСЃР»РµРґРЅРµРµ РїРѕСЏРІР»РµРЅРёРµ:</span>
                    <span className="ml-1">{formatDate(vehicle.last_seen)}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {selectedVehicle && (
            <Card className="p-6 bg-white shadow-sm">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">РСЃС‚РѕСЂРёСЏ РїРµСЂРµРјРµС‰РµРЅРёР№</h3>
              <div className="mb-4 p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-gray-900">{selectedVehicle.plate_number}</h4>
                  <Badge className={getStatusColor(statusLabel(selectedVehicle))}>
                    {statusLabel(selectedVehicle)}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
                  <div>
                    <span className="font-medium">РўРµРєСѓС‰РµРµ РјРµСЃС‚Рѕ:</span>
                    <span className="ml-1">{currentSpot(selectedVehicle.id)}</span>
                  </div>
                  <div>
                    <span className="font-medium">РџРѕСЃР»РµРґРЅРµРµ РїРѕСЏРІР»РµРЅРёРµ:</span>
                    <span className="ml-1">{formatDate(selectedVehicle.last_seen)}</span>
                  </div>
                </div>
                <div className="mt-3">
                  <Button
                    onClick={toggleBlock}
                    variant={selectedVehicle.is_blocked ? "outline" : "destructive"}
                  >
                    {selectedVehicle.is_blocked
                      ? "Р Р°Р·СЂРµС€РёС‚СЊ РґРѕСЃС‚СѓРї"
                      : "Р—Р°РїСЂРµС‚РёС‚СЊ РґРѕСЃС‚СѓРї"}
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
            <h3 className="text-lg font-medium text-gray-900 mb-2">РўСЂР°РЅСЃРїРѕСЂС‚ РЅРµ РЅР°Р№РґРµРЅ</h3>
            <p className="text-gray-600">
              РўСЂР°РЅСЃРїРѕСЂС‚ СЃ РЅРѕРјРµСЂРѕРј "{searchQuery}" РЅРµ РЅР°Р№РґРµРЅ. РџСЂРѕРІРµСЂСЊС‚Рµ РЅРѕРјРµСЂ Рё РїРѕРїСЂРѕР±СѓР№С‚Рµ СЃРЅРѕРІР°.
            </p>
          </div>
        </Card>
      )}
    </div>
  );
}
