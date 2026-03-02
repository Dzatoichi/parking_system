import React, { useState } from 'react';
import { Settings as SettingsIcon, User, Bell, Shield, Database, Wifi } from 'lucide-react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Switch } from './ui/switch';
import { Label } from './ui/label';
import { Separator } from './ui/separator';

export function Settings() {
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [pushNotifications, setPushNotifications] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [darkMode, setDarkMode] = useState(false);

  const handleSaveSettings = () => {
    // Mock save functionality
    alert('Настройки успешно сохранены!');
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900 mb-2">Настройки</h1>
        <p className="text-gray-600">Управление настройками и конфигурацией системы</p>
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* User Profile */}
        <Card className="p-6 bg-white shadow-sm">
          <div className="flex items-center space-x-3 mb-6">
            <User className="w-5 h-5 text-gray-600" />
            <h3 className="text-lg font-semibold text-gray-900">Профиль пользователя</h3>
          </div>
          
          <div className="space-y-4">
            <div>
              <Label htmlFor="username">Имя пользователя</Label>
              <Input id="username" defaultValue="Администратор" className="mt-1" />
            </div>
            
            <div>
              <Label htmlFor="email">Email адрес</Label>
              <Input id="email" type="email" defaultValue="admin@smartparking.com" className="mt-1" />
            </div>
            
            <div>
              <Label htmlFor="role">Роль</Label>
              <Input id="role" defaultValue="Системный администратор" disabled className="mt-1" />
            </div>
            
            <Button className="w-full bg-blue-600 hover:bg-blue-700">
              Обновить профиль
            </Button>
          </div>
        </Card>

        {/* Notification Settings */}
        <Card className="p-6 bg-white shadow-sm">
          <div className="flex items-center space-x-3 mb-6">
            <Bell className="w-5 h-5 text-gray-600" />
            <h3 className="text-lg font-semibold text-gray-900">Уведомления</h3>
          </div>
          
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="email-notifications">Email уведомления</Label>
                <p className="text-sm text-gray-600">Получать оповещения на email</p>
              </div>
              <Switch
                id="email-notifications"
                checked={emailNotifications}
                onCheckedChange={setEmailNotifications}
              />
            </div>
            
            <Separator />
            
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="push-notifications">Push уведомления</Label>
                <p className="text-sm text-gray-600">Уведомления в браузере</p>
              </div>
              <Switch
                id="push-notifications"
                checked={pushNotifications}
                onCheckedChange={setPushNotifications}
              />
            </div>
            
            <Separator />
            
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="auto-refresh">Автообновление</Label>
                <p className="text-sm text-gray-600">Автоматическое обновление данных</p>
              </div>
              <Switch
                id="auto-refresh"
                checked={autoRefresh}
                onCheckedChange={setAutoRefresh}
              />
            </div>
          </div>
        </Card>

        {/* System Configuration */}
        <Card className="p-6 bg-white shadow-sm">
          <div className="flex items-center space-x-3 mb-6">
            <SettingsIcon className="w-5 h-5 text-gray-600" />
            <h3 className="text-lg font-semibold text-gray-900">Конфигурация системы</h3>
          </div>
          
          <div className="space-y-4">
            <div>
              <Label htmlFor="refresh-interval">Интервал обновления (секунды)</Label>
              <Input id="refresh-interval" type="number" defaultValue="30" className="mt-1" />
            </div>
            
            <div>
              <Label htmlFor="max-duration">Макс. время парковки (часы)</Label>
              <Input id="max-duration" type="number" defaultValue="12" className="mt-1" />
            </div>
            
            <div>
              <Label htmlFor="pricing-rate">Почасовая тариф ($)</Label>
              <Input id="pricing-rate" type="number" step="0.01" defaultValue="2.50" className="mt-1" />
            </div>
            
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="dark-mode">Темная тема</Label>
                <p className="text-sm text-gray-600">Переключить на темную тему</p>
              </div>
              <Switch
                id="dark-mode"
                checked={darkMode}
                onCheckedChange={setDarkMode}
              />
            </div>
          </div>
        </Card>

        {/* Security Settings */}
        <Card className="p-6 bg-white shadow-sm">
          <div className="flex items-center space-x-3 mb-6">
            <Shield className="w-5 h-5 text-gray-600" />
            <h3 className="text-lg font-semibold text-gray-900">Безопасность</h3>
          </div>
          
          <div className="space-y-4">
            <div>
              <Label htmlFor="current-password">Текущий пароль</Label>
              <Input id="current-password" type="password" className="mt-1" />
            </div>
            
            <div>
              <Label htmlFor="new-password">Новый пароль</Label>
              <Input id="new-password" type="password" className="mt-1" />
            </div>
            
            <div>
              <Label htmlFor="confirm-password">Подтвердите пароль</Label>
              <Input id="confirm-password" type="password" className="mt-1" />
            </div>
            
            <Button variant="outline" className="w-full">
              Изменить пароль
            </Button>
          </div>
        </Card>
      </div>

      {/* System Status */}
      <Card className="p-6 bg-white shadow-sm">
        <div className="flex items-center space-x-3 mb-6">
          <Database className="w-5 h-5 text-gray-600" />
          <h3 className="text-lg font-semibold text-gray-900">Статус системы</h3>
        </div>
        
        <div className="grid grid-cols-3 gap-6">
          <div className="flex items-center space-x-3">
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <div>
              <p className="text-sm font-medium text-gray-900">База данных</p>
              <p className="text-xs text-gray-600">Подключена</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <div>
              <p className="text-sm font-medium text-gray-900">Датчики</p>
              <p className="text-xs text-gray-600">150/150 Активны</p>
            </div>
          </div>
          
          <div className="flex items-center space-x-3">
            <div className="w-3 h-3 bg-green-500 rounded-full"></div>
            <div>
              <p className="text-sm font-medium text-gray-900">Сеть</p>
              <p className="text-xs text-gray-600">Стабильна</p>
            </div>
          </div>
        </div>
        
        <Separator className="my-6" />
        
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-900">Последнее резервное копирование</p>
            <p className="text-xs text-gray-600">Сегодня в 3:00</p>
          </div>
          <Button variant="outline">
            Создать резервную копию
          </Button>
        </div>
      </Card>

      {/* Save Settings */}
      <div className="flex justify-end space-x-4">
        <Button variant="outline">
          Сбросить настройки
        </Button>
        <Button onClick={handleSaveSettings} className="bg-blue-600 hover:bg-blue-700">
          Сохранить все настройки
        </Button>
      </div>
    </div>
  );
}