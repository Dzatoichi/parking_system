import React, { useMemo, useState } from "react";
import { RefreshCw, Filter, MapPin } from "lucide-react";

import { useParkingMapData } from "../hooks/useParkingMapData";
import type { SpotReadShort } from "../services/pmApi";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

export function ParkingMap() {
  const [filter, setFilter] = useState("all");
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
        return spot.spot_status === filter;
      }),
    [filter, spots],
  );

  const getSpotColor = (status: string) => {
    switch (status) {
      case "free":
        return "bg-green-100 border-green-300 text-green-800";
      case "occupied":
        return "bg-red-100 border-red-300 text-red-800";
      default:
        return "bg-gray-100 border-gray-300 text-gray-800";
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 mb-2">РљР°СЂС‚Р° РїР°СЂРєРѕРІРєРё</h1>
          <p className="text-gray-600">
            {parking
              ? `${parking.name}, ${parking.address}`
              : "Р’РёР·СѓР°Р»РёР·Р°С†РёСЏ РїР°СЂРєРѕРІРєРё РІ СЂРµР°Р»СЊРЅРѕРј РІСЂРµРјРµРЅРё"}
          </p>
        </div>

        <div className="flex items-center space-x-4">
          <Select value={filter} onValueChange={setFilter}>
            <SelectTrigger className="w-40">
              <Filter className="w-4 h-4 mr-2" />
              <SelectValue placeholder="Р¤РёР»СЊС‚СЂ РјРµСЃС‚" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Р’СЃРµ РјРµСЃС‚Р°</SelectItem>
              <SelectItem value="free">РўРѕР»СЊРєРѕ СЃРІРѕР±РѕРґРЅС‹Рµ</SelectItem>
              <SelectItem value="occupied">РўРѕР»СЊРєРѕ Р·Р°РЅСЏС‚С‹Рµ</SelectItem>
            </SelectContent>
          </Select>

          <Button onClick={handleRefresh} variant="outline" className="flex items-center space-x-2">
            <RefreshCw className="w-4 h-4" />
            <span>РћР±РЅРѕРІРёС‚СЊ</span>
          </Button>
        </div>
      </div>
      {loading && <p className="text-sm text-gray-500">Р—Р°РіСЂСѓР·РєР° РґР°РЅРЅС‹С…...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid grid-cols-4 gap-8">
        <div className="col-span-3">
          <Card className="p-6 bg-white shadow-sm">
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">РЎС…РµРјР° РїР°СЂРєРѕРІРєРё</h3>
              <p className="text-sm text-gray-600">
                РћР±РЅРѕРІР»РµРЅРѕ: {lastRefresh.toLocaleTimeString("ru-RU")}
              </p>
            </div>

            <div className="grid grid-cols-4 gap-4">
              {filteredSpots.map((spot) => (
                <div
                  key={spot.id}
                  className={`aspect-square rounded-lg border-2 p-4 flex flex-col items-center justify-center relative transition-all duration-200 hover:scale-105 cursor-pointer ${getSpotColor(spot.spot_status)}`}
                  title={`РњРµСЃС‚Рѕ ${spot.spot_number} - ${spot.spot_status === "free" ? "СЃРІРѕР±РѕРґРЅРѕ" : "Р·Р°РЅСЏС‚Рѕ"}`}
                >
                  <div className="text-sm font-semibold mb-2">{spot.spot_number}</div>

                  {spot.spot_status === "occupied" && (
                    <>
                      <div className="text-2xl mb-1">рџљ—</div>
                      <div className="text-xs font-medium">ID {spot.current_vehicle_id ?? "-"}</div>
                    </>
                  )}

                  {spot.spot_status === "free" && <div className="text-lg">в¬њ</div>}
                </div>
              ))}
            </div>
          </Card>
        </div>

        <div className="space-y-6">
          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">РћР±РѕР·РЅР°С‡РµРЅРёСЏ</h3>
            <div className="space-y-3">
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 bg-green-500 rounded" />
                <span className="text-sm">
                  РЎРІРѕР±РѕРґРЅРѕ ({spots.filter((s) => s.spot_status === "free").length} РјРµСЃС‚)
                </span>
              </div>
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 bg-red-500 rounded" />
                <span className="text-sm">
                  Р—Р°РЅСЏС‚Рѕ ({spots.filter((s) => s.spot_status === "occupied").length} РјРµСЃС‚)
                </span>
              </div>
            </div>
          </Card>

          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">РЎС‚Р°С‚РёСЃС‚РёРєР°</h3>
            <div className="space-y-4">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Р—Р°РїРѕР»РЅРµРЅРЅРѕСЃС‚СЊ</span>
                <span className="text-sm font-semibold">
                  {spots.length
                    ? `${Math.round((spots.filter((s) => s.spot_status === "occupied").length / spots.length) * 100)}%`
                    : "-"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">РџРёРє Р·Р°РіСЂСѓР·РєРё</span>
                <span className="text-sm font-semibold">9:00 - 17:00</span>
              </div>
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">РЎСЂ. РІСЂРµРјСЏ</span>
                <span className="text-sm font-semibold">2.5 С‡Р°СЃР°</span>
              </div>
            </div>
          </Card>

          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">РђРєС‚РёРІРЅС‹Рµ РўРЎ</h3>
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
                        <p className="text-sm font-medium">РўРЎ #{spot.current_vehicle_id ?? "-"}</p>
                        <p className="text-xs text-gray-600">РњРµСЃС‚Рѕ {spot.spot_number}</p>
                      </div>
                    </div>
                    <span className="text-xs text-gray-500">Р·Р°РЅСЏС‚Рѕ</span>
                  </div>
                ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
