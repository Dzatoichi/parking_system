import React from "react";
import { Car, Clock, TrendingUp, Camera, ParkingSquare } from "lucide-react";
import { Card } from './ui/card';
import type { Screen } from "../App";

export function Dashboard({ onNavigate }: { onNavigate?: (screen: Screen) => void }) {
  const stats = [
    { label: 'Всего мест', value: '150', icon: Car, color: 'bg-blue-600' },
    { label: 'Свободно', value: '45', icon: Car, color: 'bg-green-600' },
    { label: 'Занято', value: '105', icon: Car, color: 'bg-red-600' },
  ];

  const recentEvents = [
    { type: 'entry', plate: 'A123BC', time: '14:32', action: 'Въезд на парковку' },
    { type: 'exit', plate: 'C567DF', time: '14:28', action: 'Выезд с парковки' },
    { type: 'parking', plate: 'X891YZ', time: '14:25', action: 'Припаркован на B-12' },
    { type: 'entry', plate: 'M456NP', time: '14:20', action: 'Въезд на парковку' },
    { type: 'exit', plate: 'K789QR', time: '14:15', action: 'Выезд с парковки' },
  ];

  // Mock parking spots for mini map (5x3 grid)
  const miniParkingSpots = Array.from({ length: 15 }, (_, i) => ({
    id: i + 1,
    status: Math.random() > 0.7 ? 'free' : 'occupied',
    plate: Math.random() > 0.7 ? null : `${String.fromCharCode(65 + Math.floor(Math.random() * 26))}${Math.floor(Math.random() * 900) + 100}${String.fromCharCode(65 + Math.floor(Math.random() * 26))}${String.fromCharCode(65 + Math.floor(Math.random() * 26))}`
  }));

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">Панель управления</h1>
        <p className="text-gray-600">Обзор состояния парковочной системы в реальном времени</p>
      </div>

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
                    event.type === 'entry' ? 'bg-green-500' : 
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
                title={spot.status === 'occupied' ? `Занято ${spot.plate}` : 'Свободно'}
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
            <span className="text-sm text-gray-500">Заполненность 70%</span>
          </div>
        </Card>
      </div>
    </div>
  );
}