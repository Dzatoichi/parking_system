import React, { useState } from 'react';
import { RefreshCw, Filter, MapPin } from 'lucide-react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';

export function ParkingMap() {
  const [filter, setFilter] = useState('all');
  const [lastRefresh, setLastRefresh] = useState(new Date());

  // Generate parking spots for 5x4 grid
  const parkingSpots = Array.from({ length: 20 }, (_, i) => {
    const row = String.fromCharCode(65 + Math.floor(i / 4)); // A, B, C, D, E
    const col = (i % 4) + 1;
    const isOccupied = Math.random() > 0.6;
    const licensePlates = ['A123BC', 'C567DF', 'X891YZ', 'M456NP', 'K789QR', 'P234ST', 'Q567UV', 'R890WX'];
    
    return {
      id: `${row}-${col}`,
      row,
      col,
      status: isOccupied ? 'occupied' : Math.random() > 0.9 ? 'reserved' : 'free',
      plate: isOccupied ? licensePlates[Math.floor(Math.random() * licensePlates.length)] : null,
      entryTime: isOccupied ? new Date(Date.now() - Math.random() * 4 * 60 * 60 * 1000) : null
    };
  });

  const handleRefresh = () => {
    setLastRefresh(new Date());
  };

  const filteredSpots = parkingSpots.filter(spot => {
    if (filter === 'all') return true;
    return spot.status === filter;
  });

  const getSpotColor = (status: string) => {
    switch (status) {
      case 'free':
        return 'bg-green-100 border-green-300 text-green-800';
      case 'occupied':
        return 'bg-red-100 border-red-300 text-red-800';
      case 'reserved':
        return 'bg-yellow-100 border-yellow-300 text-yellow-800';
      default:
        return 'bg-gray-100 border-gray-300 text-gray-800';
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900 mb-2">Карта парковки</h1>
          <p className="text-gray-600">Визуализация парковки в реальном времени</p>
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
              <SelectItem value="reserved">Только резерв</SelectItem>
            </SelectContent>
          </Select>
          
          <Button onClick={handleRefresh} variant="outline" className="flex items-center space-x-2">
            <RefreshCw className="w-4 h-4" />
            <span>Обновить</span>
          </Button>
        </div>
      </div>

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
              {parkingSpots.map((spot) => (
                <div
                  key={spot.id}
                  className={`aspect-square rounded-lg border-2 p-4 flex flex-col items-center justify-center relative transition-all duration-200 hover:scale-105 cursor-pointer ${getSpotColor(spot.status)}`}
                  title={`Место ${spot.id} - ${spot.status === 'free' ? 'свободно' : spot.status === 'occupied' ? 'занято' : 'резерв'}${spot.plate ? ` - ${spot.plate}` : ''}`}
                >
                  <div className="text-sm font-semibold mb-2">{spot.id}</div>
                  
                  {spot.status === 'occupied' && (
                    <>
                      <div className="text-2xl mb-1">🚗</div>
                      <div className="text-xs font-medium">{spot.plate}</div>
                    </>
                  )}
                  
                  {spot.status === 'free' && (
                    <div className="text-lg">⬜</div>
                  )}
                  
                  {spot.status === 'reserved' && (
                    <div className="text-lg">🚧</div>
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
                <span className="text-sm">Свободно (45 мест)</span>
              </div>
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 bg-red-500 rounded"></div>
                <span className="text-sm">Занято (105 мест)</span>
              </div>
              <div className="flex items-center space-x-3">
                <div className="w-4 h-4 bg-yellow-500 rounded"></div>
                <span className="text-sm">Резерв (0 мест)</span>
              </div>
            </div>
          </Card>

          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Статистика</h3>
            <div className="space-y-4">
              <div className="flex justify-between">
                <span className="text-sm text-gray-600">Заполненность</span>
                <span className="text-sm font-semibold">70%</span>
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
              {parkingSpots.filter(spot => spot.status === 'occupied').slice(0, 5).map((spot) => (
                <div key={spot.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-b-0">
                  <div className="flex items-center space-x-2">
                    <MapPin className="w-4 h-4 text-gray-400" />
                    <div>
                      <p className="text-sm font-medium">{spot.plate}</p>
                      <p className="text-xs text-gray-600">Место {spot.id}</p>
                    </div>
                  </div>
                  <span className="text-xs text-gray-500">
                    {spot.entryTime ? `${Math.floor((Date.now() - spot.entryTime.getTime()) / (1000 * 60 * 60))}ч` : ''}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}