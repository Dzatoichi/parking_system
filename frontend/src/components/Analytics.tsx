import React, { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { TrendingUp, Users, Clock } from "lucide-react";

import { useAnalyticsOverview } from "../hooks/useAnalyticsOverview";
import { Card } from "./ui/card";

export function Analytics() {
  const { analytics, error } = useAnalyticsOverview();

  const metrics = useMemo(
    () => [
      {
        label: "РЎСЂ. РґР»РёС‚РµР»СЊРЅРѕСЃС‚СЊ",
        value: `${Math.round(((analytics?.avg_duration_minutes ?? 0) / 60) * 10) / 10}С‡`,
        change: "",
        icon: Clock,
        color: "text-blue-600",
      },
      {
        label: "РџРёРє Р·Р°РїРѕР»РЅРµРЅРЅРѕСЃС‚Рё",
        value: `${Math.round(analytics?.peak_occupancy_percent ?? 0)}%`,
        change: "",
        icon: TrendingUp,
        color: "text-purple-600",
      },
      {
        label: "РЈРЅРёРєР°Р»СЊРЅС‹С… РїРѕСЃРµС‚РёС‚РµР»РµР№",
        value: String(analytics?.unique_visitors_week ?? 0),
        change: "",
        icon: Users,
        color: "text-orange-600",
      },
    ],
    [analytics],
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">РђРЅР°Р»РёС‚РёРєР° Рё РѕС‚С‡РµС‚С‹</h1>
        <p className="text-gray-600">
          Р”РµС‚Р°Р»СЊРЅР°СЏ РёРЅС„РѕСЂРјР°С†РёСЏ Рё РјРµС‚СЂРёРєРё РїСЂРѕРёР·РІРѕРґРёС‚РµР»СЊРЅРѕСЃС‚Рё
        </p>
      </div>
      {error && <p className="text-sm text-red-600">{error}</p>}

      <div className="grid grid-cols-3 gap-6">
        {metrics.map((metric, index) => {
          const Icon = metric.icon;
          return (
            <Card key={index} className="p-6 bg-white shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-gray-600">{metric.label}</p>
                  <p className="text-2xl font-bold text-gray-900 mt-1">{metric.value}</p>
                  <p className={`text-sm mt-1 ${metric.color}`}>{metric.change || "Р¶РёРІС‹Рµ РґР°РЅРЅС‹Рµ"}</p>
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
        <Card className="p-6 bg-white shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">РџРѕС‡Р°СЃРѕРІР°СЏ Р·Р°РіСЂСѓР·РєР°</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={analytics?.hourly_traffic ?? []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="hour" />
              <YAxis />
              <Tooltip />
              <Bar dataKey="vehicles" fill="#2563eb" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-6 bg-white shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">РќРµРґРµР»СЊРЅР°СЏ Р·Р°РїРѕР»РЅРµРЅРЅРѕСЃС‚СЊ</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={analytics?.weekly_occupancy ?? []}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="day" />
              <YAxis />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="occupancy"
                stroke="#2563eb"
                strokeWidth={3}
                dot={{ fill: "#2563eb", strokeWidth: 2, r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="grid grid-cols-3 gap-6">
        <Card className="p-6 bg-white shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Р”Р»РёС‚РµР»СЊРЅРѕСЃС‚СЊ РїР°СЂРєРѕРІРєРё</h3>
          <ResponsiveContainer width="100%" height={250}>
            <PieChart>
              <Pie
                data={analytics?.duration_distribution ?? []}
                cx="50%"
                cy="50%"
                outerRadius={80}
                dataKey="value"
                label={({ name, value }) => `${name}: ${value}%`}
              >
                {(analytics?.duration_distribution ?? []).map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </Card>

        <Card className="p-6 bg-white shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">РЎРµРіРѕРґРЅСЏС€РЅРёРµ РїРѕРєР°Р·Р°С‚РµР»Рё</h3>
          <div className="space-y-4">
            <div className="flex justify-between items-center py-3 border-b border-gray-100">
              <span className="text-sm text-gray-600">Р’СЃРµРіРѕ РІСЉРµР·РґРѕРІ</span>
              <span className="text-sm font-semibold">{analytics?.total_entries_today ?? 0}</span>
            </div>
            <div className="flex justify-between items-center py-3 border-b border-gray-100">
              <span className="text-sm text-gray-600">Р’СЃРµРіРѕ РІС‹РµР·РґРѕРІ</span>
              <span className="text-sm font-semibold">{analytics?.total_exits_today ?? 0}</span>
            </div>
            <div className="flex justify-between items-center py-3 border-b border-gray-100">
              <span className="text-sm text-gray-600">РўРµРєСѓС‰РёС… РўРЎ</span>
              <span className="text-sm font-semibold">{analytics?.current_vehicles ?? 0}</span>
            </div>
            <div className="flex justify-between items-center py-3 border-b border-gray-100">
              <span className="text-sm text-gray-600">РџРёРєРѕРІС‹Р№ С‡Р°СЃ</span>
              <span className="text-sm font-semibold">{analytics?.peak_hour ?? "-"}</span>
            </div>
            <div className="flex justify-between items-center py-3">
              <span className="text-sm text-gray-600">РЎСЂ. РІСЂРµРјСЏ</span>
              <span className="text-sm font-semibold">
                {analytics ? `${Math.round(analytics.avg_duration_minutes)} РјРёРЅ` : "-"}
              </span>
            </div>
          </div>
        </Card>

        <Card className="p-6 bg-white shadow-sm">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">РЎРёСЃС‚РµРјРЅС‹Рµ СѓРІРµРґРѕРјР»РµРЅРёСЏ</h3>
          <div className="space-y-3">
            <div className="flex items-start space-x-3 p-3 bg-yellow-50 rounded-lg">
              <div className="w-2 h-2 bg-yellow-500 rounded-full mt-2" />
              <div>
                <p className="text-sm font-medium text-gray-900">Р’С‹СЃРѕРєР°СЏ Р·Р°РіСЂСѓР·РєР°</p>
                <p className="text-xs text-gray-600">
                  РџР°СЂРєРѕРІРєР° Р·Р°РїРѕР»РЅРµРЅР° РЅР° {Math.round((analytics?.occupancy_rate ?? 0) * 100)}%
                </p>
                <p className="text-xs text-gray-500">2 РјРёРЅСѓС‚С‹ РЅР°Р·Р°Рґ</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 p-3 bg-blue-50 rounded-lg">
              <div className="w-2 h-2 bg-blue-500 rounded-full mt-2" />
              <div>
                <p className="text-sm font-medium text-gray-900">РќР°С‡Р°Р»Рѕ РїРёРєРѕРІРѕРіРѕ РІСЂРµРјРµРЅРё</p>
                <p className="text-xs text-gray-600">РџРёРєРѕРІС‹Р№ С‡Р°СЃ: {analytics?.peak_hour ?? "-"}</p>
                <p className="text-xs text-gray-500">1 С‡Р°СЃ РЅР°Р·Р°Рґ</p>
              </div>
            </div>

            <div className="flex items-start space-x-3 p-3 bg-green-50 rounded-lg">
              <div className="w-2 h-2 bg-green-500 rounded-full mt-2" />
              <div>
                <p className="text-sm font-medium text-gray-900">РЎС‚Р°С‚СѓСЃ СЃРёСЃС‚РµРјС‹</p>
                <p className="text-xs text-gray-600">
                  РўРµРєСѓС‰РёС… Р°РІС‚Рѕ РЅР° РїР°СЂРєРѕРІРєРµ: {analytics?.current_vehicles ?? 0}
                </p>
                <p className="text-xs text-gray-500">3 С‡Р°СЃР° РЅР°Р·Р°Рґ</p>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
