import React, { useState } from 'react';
import { Search, Clock, MapPin, Car, ArrowRight } from 'lucide-react';
import { Card } from './ui/card';
import { Input } from './ui/input';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

export function VehicleSearch() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [selectedVehicle, setSelectedVehicle] = useState<any>(null);

  // Mock data for vehicle history
  const mockVehicleData = {
    'A123BC': {
      plate: 'A123BC',
      status: 'На парковке',
      currentSpot: 'A-15',
      entryTime: '2024-10-01 08:30:00',
      duration: '6ч 15м',
      history: [
        { time: '08:30:00', action: 'Въезд', location: 'Главный шлагбаум', description: 'Транспорт въехал на парковку' },
        { time: '08:32:00', action: 'Перемещение', location: 'Секция A', description: 'Движение к месту парковки' },
        { time: '08:35:00', action: 'Припаркован', location: 'Место A-15', description: 'Транспорт припаркован на месте' },
      ]
    },
    'C567DF': {
      plate: 'C567DF',
      status: 'Выехал',
      currentSpot: null,
      entryTime: '2024-10-01 09:15:00',
      exitTime: '2024-10-01 12:30:00',
      duration: '3ч 15м',
      history: [
        { time: '09:15:00', action: 'Въезд', location: 'Главный шлагбаум', description: 'Транспорт въехал на парковку' },
        { time: '09:18:00', action: 'Перемещение', location: 'Секция B', description: 'Движение к месту парковки' },
        { time: '09:20:00', action: 'Припаркован', location: 'Место B-08', description: 'Транспорт припаркован на месте' },
        { time: '12:28:00', action: 'Перемещение', location: 'Секция B', description: 'Транспорт покидает место' },
        { time: '12:30:00', action: 'Выезд', location: 'Главный шлагбаум', description: 'Транспорт выехал с парковки' },
      ]
    },
    'X891YZ': {
      plate: 'X891YZ',
      status: 'На парковке',
      currentSpot: 'B-12',
      entryTime: '2024-10-01 10:45:00',
      duration: '4ч 0м',
      history: [
        { time: '10:45:00', action: 'Въезд', location: 'Главный шлагбаум', description: 'Транспорт въехал на парковку' },
        { time: '10:48:00', action: 'Перемещение', location: 'Секция B', description: 'Движение к месту парковки' },
        { time: '10:50:00', action: 'Припаркован', location: 'Место B-12', description: 'Транспорт припаркован на месте' },
      ]
    }
  };

  const handleSearch = () => {
    if (searchQuery.trim()) {
      const results = Object.values(mockVehicleData).filter(vehicle =>
        vehicle.plate.toLowerCase().includes(searchQuery.toLowerCase())
      );
      setSearchResults(results);
      if (results.length === 1) {
        setSelectedVehicle(results[0]);
      }
    } else {
      setSearchResults([]);
      setSelectedVehicle(null);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'На парковке':
        return 'bg-green-100 text-green-800';
      case 'Выехал':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-blue-100 text-blue-800';
    }
  };

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'Въезд':
        return <ArrowRight className="w-4 h-4 text-green-600 rotate-180" />;
      case 'Выезд':
        return <ArrowRight className="w-4 h-4 text-red-600" />;
      case 'Припаркован':
        return <Car className="w-4 h-4 text-blue-600" />;
      case 'Перемещение':
        return <MapPin className="w-4 h-4 text-yellow-600" />;
      default:
        return <Clock className="w-4 h-4 text-gray-600" />;
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">Поиск транспорта</h1>
        <p className="text-gray-600">Поиск транспортных средств и просмотр истории перемещений</p>
      </div>

      {/* Search Section */}
      <Card className="p-6 bg-white shadow-sm">
        <div className="flex items-center space-x-4">
          <div className="flex-1">
            <Input
              type="text"
              placeholder="Введите номер транспорта..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              className="w-full"
            />
          </div>
          <Button onClick={handleSearch} className="bg-blue-600 hover:bg-blue-700">
            <Search className="w-4 h-4 mr-2" />
            Поиск
          </Button>
        </div>

        {/* Quick Search Suggestions */}
        <div className="mt-4">
          <p className="text-sm text-gray-600 mb-2">Быстрый поиск:</p>
          <div className="flex space-x-2">
            {Object.keys(mockVehicleData).map((plate) => (
              <Button
                key={plate}
                variant="outline"
                size="sm"
                onClick={() => {
                  setSearchQuery(plate);
                  setSearchResults([mockVehicleData[plate as keyof typeof mockVehicleData]]);
                  setSelectedVehicle(mockVehicleData[plate as keyof typeof mockVehicleData]);
                }}
              >
                {plate}
              </Button>
            ))}
          </div>
        </div>
      </Card>

      {/* Search Results */}
      {searchResults.length > 0 && (
        <div className="grid grid-cols-2 gap-6">
          <Card className="p-6 bg-white shadow-sm">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Результаты поиска</h3>
            <div className="space-y-4">
              {searchResults.map((vehicle, index) => (
                <div
                  key={index}
                  onClick={() => setSelectedVehicle(vehicle)}
                  className={`p-4 border rounded-lg cursor-pointer transition-all duration-200 ${
                    selectedVehicle?.plate === vehicle.plate
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="font-semibold text-gray-900">{vehicle.plate}</h4>
                    <Badge className={getStatusColor(vehicle.status)}>
                      {vehicle.status}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
                    <div>
                      <span className="font-medium">Место:</span> 
                      <span className="ml-1">{vehicle.currentSpot || 'Н/Д'}</span>
                    </div>
                    <div>
                      <span className="font-medium">Длительность:</span> 
                      <span className="ml-1">{vehicle.duration}</span>
                    </div>
                  </div>
                  <div className="mt-2 text-sm text-gray-600">
                    <span className="font-medium">Въезд:</span> 
                    <span className="ml-1">{vehicle.entryTime}</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Vehicle Details and History */}
          {selectedVehicle && (
            <Card className="p-6 bg-white shadow-sm">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">История перемещений</h3>
              <div className="mb-4 p-4 bg-gray-50 rounded-lg">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-gray-900">{selectedVehicle.plate}</h4>
                  <Badge className={getStatusColor(selectedVehicle.status)}>
                    {selectedVehicle.status}
                  </Badge>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
                  <div>
                    <span className="font-medium">Текущее место:</span> 
                    <span className="ml-1">{selectedVehicle.currentSpot || 'Выехал'}</span>
                  </div>
                  <div>
                    <span className="font-medium">Общее время:</span> 
                    <span className="ml-1">{selectedVehicle.duration}</span>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                {selectedVehicle.history.map((event: any, index: number) => (
                  <div key={index} className="flex items-start space-x-4">
                    <div className="flex-shrink-0 w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
                      {getActionIcon(event.action)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-gray-900">
                          {event.action} - {event.location}
                        </p>
                        <span className="text-xs text-gray-500">{event.time}</span>
                      </div>
                      <p className="text-sm text-gray-600 mt-1">{event.description}</p>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}

      {/* No Results */}
      {searchQuery && searchResults.length === 0 && (
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