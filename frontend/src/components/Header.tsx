import React from 'react';
import { Bell, User } from 'lucide-react';
import { Badge } from './ui/badge';

export function Header() {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
      <div className="flex items-center">
        <div className="flex items-center space-x-3">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <div className="w-4 h-4 bg-white rounded-sm"></div>
          </div>
          <h1 className="text-xl font-semibold text-gray-900">Умная Парковка</h1>
        </div>
      </div>
      
      <div className="flex items-center space-x-4">
        <div className="relative">
          <Bell className="w-6 h-6 text-gray-600 hover:text-gray-900 cursor-pointer" />
          <Badge className="absolute -top-2 -right-2 w-5 h-5 p-0 flex items-center justify-center bg-red-600 text-white text-xs">
            3
          </Badge>
        </div>
        
        <div className="flex items-center space-x-3 pl-4 border-l border-gray-200">
          <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center">
            <User className="w-5 h-5 text-gray-600" />
          </div>
          <span className="text-sm font-medium text-gray-900">Администратор</span>
        </div>
      </div>
    </header>
  );
}