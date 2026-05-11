import React from 'react';
import {
  LayoutDashboard,
  Map,
  Search,
  BarChart3,
  Settings as SettingsIcon,
  Camera,
  ParkingSquare,
  CalendarDays,
} from 'lucide-react';
import type { Screen } from '../app/screens';

interface SidebarProps {
  currentScreen: Screen;
  onScreenChange: (screen: Screen) => void;
}

const mainMenuItems = [
  { id: 'dashboard' as Screen, label: 'Панель управления', icon: LayoutDashboard },
  { id: 'parking-map' as Screen, label: 'Карта парковки', icon: Map },
  { id: 'vehicle-search' as Screen, label: 'Поиск транспорта', icon: Search },
  { id: 'analytics' as Screen, label: 'Аналитика', icon: BarChart3 },
  { id: 'bookings' as Screen, label: 'Журнал бронирований', icon: CalendarDays },
];

const toolsMenuItems = [
  { id: 'cameras-network' as Screen, label: 'Сеть камер', icon: Camera },
  { id: 'parking-marker' as Screen, label: 'Разметка мест', icon: ParkingSquare },
];

const bottomMenuItems = [
  { id: 'settings' as Screen, label: 'Настройки', icon: SettingsIcon },
];

export function Sidebar({ currentScreen, onScreenChange }: SidebarProps) {
  const renderItem = (item: { id: Screen; label: string; icon: React.ElementType }) => {
    const Icon = item.icon;
    const isActive = currentScreen === item.id;

    return (
      <button
        key={item.id}
        onClick={() => onScreenChange(item.id)}
        className={`w-full flex items-center space-x-3 px-4 py-3 rounded-lg transition-all duration-200 ${
          isActive
            ? 'bg-blue-600 text-white shadow-sm'
            : 'text-gray-700 hover:bg-gray-100'
        }`}
      >
        <Icon className="w-5 h-5 shrink-0" />
        <span className="font-medium text-sm">{item.label}</span>
      </button>
    );
  };

  return (
    <aside className="w-64 bg-white border-r border-gray-200 flex flex-col">
      <nav className="flex-1 p-4 space-y-1">
        {mainMenuItems.map(renderItem)}

        <div className="pt-4 pb-1">
          <p className="px-4 text-xs font-semibold text-gray-400 uppercase tracking-wider">
            Инструменты
          </p>
        </div>

        {toolsMenuItems.map(renderItem)}
      </nav>

      <div className="p-4 border-t border-gray-200">
        {bottomMenuItems.map(renderItem)}
      </div>
    </aside>
  );
}
