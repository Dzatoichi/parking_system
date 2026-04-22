import React, { useEffect, useMemo, useState } from "react";
import { Car, Clock, TrendingUp, Camera, ParkingSquare } from "lucide-react";
import { Card } from './ui/card';
import type { Screen } from "../App";
import { analyticsApi, parkingApi, spotApi } from "../services/pmApi";
import type { AnalyticsOverview, ParkingRead, ParkingStats } from "../services/pmApi";

export function Dashboard({ onNavigate }: { onNavigate?: (screen: Screen) => void }) {
  const [parking, setParking] = useState<ParkingRead | null>(null);
  const [statsData, setStatsData] = useState<ParkingStats | null>(null);
  const [analytics, setAnalytics] = useState<AnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true);
      setError(null);
      try {
        const parkingRes = await parkingApi.getAll({ only_active: true, page: 1, size: 1 });
        const firstParking = parkingRes.data.items[0];
        if (!firstParking) {
          setError("Нет активных парковок. Добавьте данные в БД.");
          return;
        }
        setParking(firstParking);
        const statsRes = await spotApi.getStats(firstParking.id);
        setStatsData(statsRes.data);
        const analyticsRes = await analyticsApi.getOverview(firstParking.id);
        setAnalytics(analyticsRes.data);
      } catch (e: any) {
        setError(e?.response?.data?.detail ?? e?.message ?? "Ошибка загрузки данных");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    const timer = setInterval(fetchData, 30000);
    return () => clearInterval(timer);
  }, []);

  const stats = useMemo(() => {
    if (!statsData) {
      return [
        { label: 'Всего мест', value: '-', icon: Car, color: 'bg-blue-600' },
        { label: 'Свободно', value: '-', icon: Car, color: 'bg-green-600' },
        { label: 'Занято', value: '-', icon: Car, color: 'bg-red-600' },
      ];
    }
    return [
      { label: 'Всего мест', value: String(statsData.total_spots), icon: Car, color: 'bg-blue-600' },
      { label: 'Свободно', value: String(statsData.free), icon: Car, color: 'bg-green-600' },
      { label: 'Занято', value: String(statsData.occupied), icon: Car, color: 'bg-red-600' },
    ];
  }, [statsData]);

  const recentEvents = analytics?.recent_events ?? [];
  const miniParkingSpots = analytics?.mini_spots ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">Панель управления</h1>
        <p className="text-gray-600">
          {parking ? `Обзор: ${parking.name}, ${parking.address}` : "Обзор состояния парковочной системы в реальном времени"}
        </p>
      </div>
      {loading && <p className="text-sm text-gray-500">Загрузка данных...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      {/* Quick actions */}
      <div className="grid grid-cols-2 gap-6">
        <Card className="p-6 bg-white shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Инструменты</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">
                Разметка мест
              </p>
              <p className="text-sm text-gray-500 mt-1">
                Создание/обновление разметки парковочных мест
              </p>
            </div>
            <div className="w-12 h-12 bg-blue-600 rounded-lg flex items-center justify-center">
              <ParkingSquare className="w-6 h-6 text-white" />
            </div>
          </div>
          <button
            onClick={() => onNavigate?.("parking-marker")}
            className="mt-4 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Открыть
          </button>
        </Card>

        <Card className="p-6 bg-white shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Инструменты</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">
                Настройка камер
              </p>
              <p className="text-sm text-gray-500 mt-1">
                Добавление RTSP и калибровка
              </p>
            </div>
            <div className="w-12 h-12 bg-blue-600 rounded-lg flex items-center justify-center">
              <Camera className="w-6 h-6 text-white" />
            </div>
          </div>
          <button
            onClick={() => onNavigate?.("cameras-network")}
            className="mt-4 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            Открыть
          </button>
        </Card>
      </div>

      {/* Statistics Cards */}
      <div className="grid grid-cols-3 gap-6">
        {stats.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <Card key={index} className="p-6 bg-white shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">{stat.label}</p>
                  <p className="text-3xl font-bold text-gray-900 mt-2">{stat.value}</p>
                </div>
                <div className={`w-12 h-12 ${stat.color} rounded-lg flex items-center justify-center`}>
                  <Icon className="w-6 h-6 text-white" />
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Recent Events */}
        <Card className="p-6 bg-white shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Последние события</h3>
            <Clock className="w-5 h-5 text-gray-400" />
          </div>
          <div className="space-y-3">
            {recentEvents.map((event, index) => (
              <div key={index} className="flex items-center justify-between py-3 border-b border-gray-100 last:border-b-0">
                <div className="flex items-center space-x-3">
                  <div className={`w-2 h-2 rounded-full ${
                    event.type === 'enter' ? 'bg-green-500' :
                    event.type === 'exit' ? 'bg-red-500' : 'bg-blue-500'
                  }`}></div>
                  <div>
                    <p className="text-sm font-medium text-gray-900">{event.plate}</p>
                    <p className="text-xs text-gray-600">{event.action}</p>
                  </div>
                </div>
                <span className="text-xs text-gray-500">{event.time}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Mini Parking Map */}
        <Card className="p-6 bg-white shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Обзор парковки</h3>
            <TrendingUp className="w-5 h-5 text-gray-400" />
          </div>
          <div className="grid grid-cols-5 gap-2">
            {miniParkingSpots.map((spot) => (
              <div
                key={spot.id}
                className={`aspect-square rounded-md flex items-center justify-center text-xs font-medium ${
                  spot.status === 'free' 
                    ? 'bg-green-100 text-green-800 border-2 border-green-200' 
                    : 'bg-red-100 text-red-800 border-2 border-red-200'
                }`}
                title={spot.status === 'occupied' ? `Занято ${spot.plate ?? ""}` : 'Свободно'}
              >
                {spot.status === 'occupied' ? '🚗' : ''}
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-green-500 rounded-full"></div>
                <span className="text-sm text-gray-600">Свободно</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-red-500 rounded-full"></div>
                <span className="text-sm text-gray-600">Занято</span>
              </div>
            </div>
            <span className="text-sm text-gray-500">
              Заполненность {statsData ? `${Math.round(statsData.occupancy_rate * 100)}%` : "-"}
            </span>
          </div>
        </Card>
      </div>
    </div>
  );
}