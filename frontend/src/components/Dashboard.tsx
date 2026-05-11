import React, { useMemo } from "react";
import { Car, Clock, TrendingUp, Camera, ParkingSquare } from "lucide-react";

import type { Screen } from "../app/screens";
import { useDashboardData } from "../hooks/useDashboardData";
import { Card } from "./ui/card";

export function Dashboard({ onNavigate }: { onNavigate?: (screen: Screen) => void }) {
  const { analytics, error, loading, parking, stats: statsData } = useDashboardData();

  const stats = useMemo(() => {
    if (!statsData) {
      return [
        { label: "Всего мест", value: "-", icon: Car, color: "bg-blue-600" },
        { label: "Свободно", value: "-", icon: Car, color: "bg-green-600" },
        { label: "Занято", value: "-", icon: Car, color: "bg-red-600" },
        { label: "Забронировано", value: "-", icon: Car, color: "bg-yellow-500" }
      ];
    }

    return [
      {
        label: "Всего мест",
        value: String(statsData.total_spots),
        icon: Car,
        color: "bg-blue-600",
      },
      {
        label: "Свободно",
        value: String(statsData.free),
        icon: Car,
        color: "bg-green-600",
      },
      {
        label: "Занято",
        value: String(statsData.occupied),
        icon: Car,
        color: "bg-red-600",
      },
      { 
        label: "Забронировано",
        value: String(statsData.reserved), 
        icon: Car, 
        color: "bg-yellow-500" 
      },
    ];
  }, [statsData]);

  const recentEvents = analytics?.recent_events ?? [];
  const miniParkingSpots = analytics?.mini_spots ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">Панель управления</h1>
        <p className="text-gray-600">
          {parking
            ? `Обзор: ${parking.name}, ${parking.address}`
            : "Обзор состояния парковочной системы в реальном времени"}
        </p>
      </div>
      {loading && <p className="text-sm text-gray-500">Загрузка данных...</p>}
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid grid-cols-2 gap-6">
        <Card className="p-6 bg-white shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Инструменты</p>
              <p className="text-lg font-semibold text-gray-900 mt-1">Разметка мест</p>
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
              <p className="text-lg font-semibold text-gray-900 mt-1">Настройка камер</p>
              <p className="text-sm text-gray-500 mt-1">Добавление RTSP и калибровка</p>
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

      <div className="grid grid-cols-4 gap-6">
        {stats.map((stat, index) => {
          const Icon = stat.icon;
          return (
            <Card key={index} className="p-6 bg-white shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">{stat.label}</p>
                  <p className="text-3xl font-bold text-gray-900 mt-2">{stat.value}</p>
                </div>
                <div
                  className={`w-12 h-12 ${stat.color} rounded-lg flex items-center justify-center`}
                >
                  <Icon className="w-6 h-6 text-white" />
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-6">
        <Card className="p-6 bg-white shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Последние события</h3>
            <Clock className="w-5 h-5 text-gray-400" />
          </div>
          <div className="space-y-3">
            {recentEvents.map((event, index) => (
              <div
                key={index}
                className="flex items-center justify-between py-3 border-b border-gray-100 last:border-b-0"
              >
                <div className="flex items-center space-x-3">
                  <div
                    className={`w-2 h-2 rounded-full ${
                      event.type === "enter"
                        ? "bg-green-500"
                        : event.type === "exit"
                          ? "bg-red-500"
                          : "bg-blue-500"
                    }`}
                  />
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
                  spot.status === "free"
                    ? "bg-green-100 text-green-800 border-2 border-green-200"
                    : "bg-red-100 text-red-800 border-2 border-red-200"
                }`}
                title={spot.status === "occupied" ? `Занято ${spot.plate ?? ""}` : "Свободно"}
              >
                {spot.status === "occupied" ? "🚗" : ""}
              </div>
            ))}
          </div>
          <div className="flex items-center justify-between mt-4 pt-4 border-t border-gray-100">
            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-green-500 rounded-full" />
                <span className="text-sm text-gray-600">Свободно</span>
              </div>
              <div className="flex items-center space-x-2">
                <div className="w-3 h-3 bg-red-500 rounded-full" />
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
