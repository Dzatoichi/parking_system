import React from 'react';
import { 
  LayoutDashboard, 
  Map, 
  Search, 
  BarChart3, 
  Settings as SettingsIcon 
} from 'lucide-react';
import { Screen } from '../App';

interface SidebarProps {
  currentScreen: Screen;
  onScreenChange: (screen: Screen) => void;
}

const menuItems = [
  { id: 'dashboard' as Screen, label: 'Панель управления', icon: LayoutDashboard },
  { id: 'parking-map' as Screen, label: 'Карта парковки', icon: Map },
  { id: 'vehicle-search' as Screen, label: 'Поиск транспорта', icon: Search },
  { id: 'analytics' as Screen, label: 'Аналитика', icon: BarChart3 },
  { id: 'settings' as Screen, label: 'Настройки', icon: SettingsIcon },
];

export function Sidebar({ currentScreen, onScreenChange }: SidebarProps) {
  return (
    <aside className="w-64 bg-white border-r border-gray-200 p-4">
      <nav className="space-y-2">
        {menuItems.map((item) => {
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
              <Icon className="w-5 h-5" />
              <span className="font-medium">{item.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
}