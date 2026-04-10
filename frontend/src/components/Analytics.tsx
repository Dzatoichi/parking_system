import React from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line, PieChart, Pie, Cell } from 'recharts';
import { TrendingUp, Users, Clock } from 'lucide-react';
import { Card } from './ui/card';

export function Analytics() {
  // Mock data for charts
  const hourlyData = [
    { hour: '6:00', vehicles: 12 },
    { hour: '8:00', vehicles: 45 },
    { hour: '10:00', vehicles: 78 },
    { hour: '12:00', vehicles: 95 },
    { hour: '14:00', vehicles: 88 },
    { hour: '16:00', vehicles: 102 },
    { hour: '18:00', vehicles: 67 },
    { hour: '20:00', vehicles: 34 },
    { hour: '22:00', vehicles: 18 },
  ];

  const weeklyData = [
    { day: 'Пн', occupancy: 85 },
    { day: 'Вт', occupancy: 92 },
    { day: 'Ср', occupancy: 78 },
    { day: 'Чт', occupancy: 88 },
    { day: 'Пт', occupancy: 96 },
    { day: 'Сб', occupancy: 45 },
    { day: 'Вс', occupancy: 32 },
  ];

  const durationData = [
    { name: '< 1 часа', value: 25, color: '#16a34a' },
    { name: '1-3 часа', value: 45, color: '#2563eb' },
    { name: '3-6 часов', value: 20, color: '#f59e0b' },
    { name: '> 6 часов', value: 10, color: '#dc2626' },
  ];

  const metrics = [
    { label: 'Ср. длительность', value: '2.5ч', change: '+5%', icon: Clock, color: 'text-blue-600' },
    { label: 'Пик заполненности', value: '96%', change: '+3%', icon: TrendingUp, color: 'text-purple-600' },
    { label: 'Уникальных посетителей', value: '234', change: '+8%', icon: Users, color: 'text-orange-600' },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">Аналитика и отчеты</h1>
        <p className="text-gray-600">Детальная информация и метрики производительности</p>
      </div>

      {/* Key Metrics */}
      <div className="grid grid-cols-3 gap-6">
        {metrics.map((metric, index) => {
          const Icon = metric.icon;
          return (
            <Card key={index} className="p-6 bg-white shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">{metric.label}</p>
                  <p className="text-2xl font-bold text-gray-900 mt-1">{metric.value}</p>
                  <p className={`text-sm mt-1 ${metric.color}`}>{metric.change} за неделю</p>
                </div>
                <div className="w-10 h-10 bg-gray-100 rounded-lg flex items-center justify-center">
                  <Icon className="w-5 h-5 text-gray-600" />
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Hourly Traffic */}
        <Card className="p-6 bg-white shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Почасовая загрузка</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={hourlyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="hour" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="vehicles" fill="#2563eb" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        {/* Weekly Occupancy */}
        <Card className="p-6 bg-white shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Недельная заполненность</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={weeklyData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" />
              <YAxis />
              <Tooltip />
              <Line 
                type="monotone" 
                dataKey="occupancy" 
                stroke="#2563eb" 
                strokeWidth={3}
                dot={{ fill: '#2563eb', strokeWidth: 2, r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Parking Duration Distribution */}
        <Card className="p-6 bg-white shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Длительность парковки</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={durationData}
                cx="50%"
                cy="50%"
                outerRadius={80}
                dataKey="value"
                label={({ name, value }) => `${name}: ${value}%`}
              >
                {durationData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        {/* Top Statistics */}
        <Card className="p-6 bg-white shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Сегодняшние показатели</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center py-3 border-b border-gray-100">
              <span className="text-sm text-gray-600">Всего въездов</span>
              <span className="text-sm font-semibold">127</span>
            </div>
            <div className="flex justify-between items-center py-3 border-b border-gray-100">
              <span className="text-sm text-gray-600">Всего выездов</span>
              <span className="text-sm font-semibold">98</span>
            </div>
            <div className="flex justify-between items-center py-3 border-b border-gray-100">
              <span className="text-sm text-gray-600">Текущих ТС</span>
              <span className="text-sm font-semibold">105</span>
            </div>
            <div className="flex justify-between items-center py-3 border-b border-gray-100">
              <span className="text-sm text-gray-600">Пиковый час</span>
              <span className="text-sm font-semibold">16:00</span>
            </div>
            <div className="flex justify-between items-center py-3">
              <span className="text-sm text-gray-600">Ср. время</span>
              <span className="text-sm font-semibold">2ч 34м</span>
            </div>
          </div>
        </Card>

        {/* Recent Alerts */}
        <Card className="p-6 bg-white shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Системные уведомления</h3>
          <div className="space-y-3">
            <div className="flex items-start space-x-3 p-3 bg-yellow-50 rounded-lg">
              <div className="w-2 h-2 bg-yellow-500 rounded-full mt-2"></div>
              <div>
                <p className="text-sm font-medium text-gray-900">Высокая загрузка</p>
                <p className="text-xs text-gray-600">Парковка заполнена на 96%</p>
                <p className="text-xs text-gray-500">2 минуты назад</p>
              </div>
            </div>
            
            <div className="flex items-start space-x-3 p-3 bg-blue-50 rounded-lg">
              <div className="w-2 h-2 bg-blue-500 rounded-full mt-2"></div>
              <div>
                <p className="text-sm font-medium text-gray-900">Начало пикового времени</p>
                <p className="text-xs text-gray-600">Обнаружен вечерний трафик</p>
                <p className="text-xs text-gray-500">1 час назад</p>
              </div>
            </div>
            
            <div className="flex items-start space-x-3 p-3 bg-green-50 rounded-lg">
              <div className="w-2 h-2 bg-green-500 rounded-full mt-2"></div>
              <div>
                <p className="text-sm font-medium text-gray-900">Статус системы</p>
                <p className="text-xs text-gray-600">Все датчики работают</p>
                <p className="text-xs text-gray-500">3 часа назад</p>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}