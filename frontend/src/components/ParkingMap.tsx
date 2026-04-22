import React, { useEffect, useMemo, useState } from 'react';
import { RefreshCw, Filter, MapPin } from 'lucide-react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { parkingApi, spotApi } from '../services/pmApi';
import type { ParkingRead, SpotReadShort } from '../services/pmApi';

export function ParkingMap() {
  const [filter, setFilter] = useState('all');
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [parking, setParking] = useState<ParkingRead | null>(null);
  const [spots, setSpots] = useState<SpotReadShort[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const parkingRes = await parkingApi.getAll({ only_active: true, page: 1, size: 1 });
      const firstParking = parkingRes.data.items[0];
      if (!firstParking) {
        setError("Нет активных парковок. Добавьте данные в БД.");
        setSpots([]);
        return;
      }
      setParking(firstParking);
      const spotsRes = await spotApi.getByParking(firstParking.id, { page: 1, size: 200 });
      setSpots(
        spotsRes.data.items.map((spot) =>
          spot.spot_status === 'reserved' ? { ...spot, spot_status: 'occupied' } : spot
        )
      );
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? "Ошибка загрузки данных");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleRefresh = async () => {
    await loadData();
    setLastRefresh(new Date());
  };

  const filteredSpots = useMemo(() => spots.filter((spot) => {
    if (filter === 'all') return true;
    return spot.spot_status === filter;
  }), [filter, spots]);

  const getSpotColor = (status: string) => {
    switch (status) {
      case 'free':
        return 'bg-green-100 border-green-300 text-green-800';
      case 'occupied':
        return 'bg-red-100 border-red-300 text-red-800';
      default:
        return 'bg-gray-100 border-gray-300 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 mb-2">Карта парковки</h1>
          <p className="text-gray-600">
            {parking ? `${parking.name}, ${parking.address}` : 'Визуализация парковки в реальном времени'}
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
        {/* Parking Grid */}
        <div className="col-span-3">
          <Card className="p-6 bg-white shadow-sm">
            <div className="mb-4">
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Схема парковки</h3>
              <p className="text-sm text-gray-600">
                Обновлено: {lastRefresh.toLocaleTimeString('ru-RU')}
              </p>
            </div>
            
            <div className="grid grid-cols-4 gap-4">
              {filteredSpots.map((spot) => (
                <div
                  key={spot.id}
                  className={`aspect-square rounded-lg border-2 p-4 flex flex-col items-center justify-center relative transition-all duration-200 hover:scale-105 cursor-pointer ${getSpotColor(spot.spot_status)}`}
                  title={`Место ${spot.spot_number} - ${spot.spot_status === 'free' ? 'свободно' : 'занято'}`}
                >
                  <div className="text-sm font-semibold mb-2">{spot.spot_number}</div>
                  
                  {spot.spot_status === 'occupied' && (
                    <>
                      <div className="text-2xl mb-1">🚗</div>
                      <div className="text-xs font-medium">ID {spot.current_vehicle_id ?? '-'}</div>
                    </>
                  )}
                  
                  {spot.spot_status === 'free' && (
                    <div className="text-lg">⬜</div>
                  )}
                  
                </div>
              ))}
            </div>
          </Card>
        </div>

        {/* Legend and Stats */}
        <div className="space-y-6">
          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Обозначения</h3>
            <div className="space-y-3">
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 bg-green-500 rounded"></div>
                <span className="text-sm">Свободно ({spots.filter((s) => s.spot_status === 'free').length} мест)</span>
              </div>
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 bg-red-500 rounded"></div>
                <span className="text-sm">Занято ({spots.filter((s) => s.spot_status === 'occupied').length} мест)</span>
              </div>
            </div>
          </Card>

          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Статистика</h3>
            <div className="space-y-4">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Заполненность</span>
                <span className="text-sm font-semibold">
                  {spots.length ? `${Math.round((spots.filter((s) => s.spot_status === 'occupied').length / spots.length) * 100)}%` : '-'}
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
            </div>
          </Card>

          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Активные ТС</h3>
            <div className="space-y-3">
              {spots.filter((spot) => spot.spot_status === 'occupied').slice(0, 5).map((spot) => (
                <div key={spot.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-b-0">
                  <div className="flex items-center space-x-2">
                    <MapPin className="w-4 h-4 text-gray-400" />
                    <div>
                      <p className="text-sm font-medium">ТС #{spot.current_vehicle_id ?? '-'}</p>
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