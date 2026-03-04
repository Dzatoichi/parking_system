import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Camera, Settings, Link, LayoutDashboard, Plus, Pencil, Trash2, X, Check, AlertCircle } from 'lucide-react';
import { camerasAPI, segmentsConfigAPI, connectionsAPI, networkAPI, Camera as CameraType, SegmentsConfig } from '../../services/camerasApi';

type CameraView = 'dashboard' | 'cameras' | 'configs' | 'connections';

export function CameraNetwork() {
  const [activeView, setActiveView] = useState<CameraView>('dashboard');

  const views = [
    { id: 'dashboard' as CameraView, label: 'Панель', icon: LayoutDashboard },
    { id: 'cameras' as CameraView, label: 'Камеры', icon: Camera },
    { id: 'configs' as CameraView, label: 'Конфигурации', icon: Settings },
    { id: 'connections' as CameraView, label: 'Подключения', icon: Link },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Sub-navigation */}
      <div className="bg-white border-b border-gray-200 px-6">
        <div className="flex items-center space-x-1">
          <div className="flex items-center space-x-2 py-3 pr-6 border-r border-gray-200 mr-2">
            <div className="w-7 h-7 bg-blue-600 rounded-md flex items-center justify-center">
              <Camera className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-gray-900 text-sm">Сеть камер</span>
          </div>
          {views.map((view) => {
            const Icon = view.icon;
            const isActive = activeView === view.id;
            return (
              <button
                key={view.id}
                onClick={() => setActiveView(view.id)}
                className={`flex items-center space-x-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors duration-200 ${
                  isActive
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300'
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{view.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {activeView === 'dashboard' && <CamerasDashboard />}
        {activeView === 'cameras' && <CamerasManager />}
        {activeView === 'configs' && <ConfigsManager />}
        {activeView === 'connections' && <ConnectionsManager />}
      </div>
    </div>
  );
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
function CamerasDashboard() {
  const { data: cameras } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => camerasAPI.getAll(),
    retry: false,
  });

  const { data: configs } = useQuery({
    queryKey: ['segmentsConfigs'],
    queryFn: () => segmentsConfigAPI.getAll(),
    retry: false,
  });

  const { data: connections } = useQuery({
    queryKey: ['connections'],
    queryFn: () => connectionsAPI.getAll(),
    retry: false,
  });

  const camerasCount = cameras?.data?.data?.length ?? 0;
  const configsCount = configs?.data?.data?.length ?? 0;
  const connectionsCount = connections?.data?.data?.length ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">Панель управления</h2>
        <p className="text-sm text-gray-500 mt-1">Обзор состояния сети камер</p>
      </div>

      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Камеры" value={camerasCount} icon={Camera} color="blue" />
        <StatCard label="Конфигурации" value={configsCount} icon={Settings} color="green" />
        <StatCard label="Подключения" value={connectionsCount} icon={Link} color="purple" />
      </div>

      {camerasCount === 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-start space-x-3">
          <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-blue-800">Начните настройку</p>
            <p className="text-sm text-blue-700 mt-1">
              Для начала работы создайте конфигурацию сегментов, затем добавьте камеры и настройте подключения между ними.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, icon: Icon, color }: { label: string; value: number; icon: React.ElementType; color: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-600 border-blue-100',
    green: 'bg-green-50 text-green-600 border-green-100',
    purple: 'bg-purple-50 text-purple-600 border-purple-100',
  };
  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-500">{label}</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
        </div>
        <div className={`w-12 h-12 rounded-lg border flex items-center justify-center ${colors[color]}`}>
          <Icon className="w-6 h-6" />
        </div>
      </div>
    </div>
  );
}

// ─── Cameras Manager ──────────────────────────────────────────────────────────
function CamerasManager() {
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<CameraType | null>(null);
  const [form, setForm] = useState({ video_path: '', clear_image_path: '', segments_config_id: '' });
  const qc = useQueryClient();

  const { data: cameras, isLoading } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => camerasAPI.getAll(),
    retry: false,
  });

  const { data: configs } = useQuery({
    queryKey: ['segmentsConfigs'],
    queryFn: () => segmentsConfigAPI.getAll(),
    retry: false,
  });

  const saveMutation = useMutation({
    mutationFn: (data: typeof form) => {
      const payload = { ...data, segments_config_id: Number(data.segments_config_id) };
      return editing ? camerasAPI.update(editing.id, payload) : camerasAPI.create(payload as any);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['cameras'] }); closeForm(); },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => camerasAPI.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cameras'] }),
  });

  const openForm = (camera?: CameraType) => {
    if (camera) {
      setEditing(camera);
      setForm({ video_path: camera.video_path, clear_image_path: camera.clear_image_path, segments_config_id: String(camera.segments_config_id) });
    } else {
      setEditing(null);
      setForm({ video_path: '', clear_image_path: '', segments_config_id: String(configs?.data?.data?.[0]?.id ?? '') });
    }
    setShowForm(true);
  };

  const closeForm = () => { setShowForm(false); setEditing(null); };

  const configsList: SegmentsConfig[] = configs?.data?.data ?? [];
  const camerasList: CameraType[] = cameras?.data?.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Управление камерами</h2>
          <p className="text-sm text-gray-500 mt-0.5">Добавление и настройка камер в сети</p>
        </div>
        <button
          onClick={() => openForm()}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Добавить камеру</span>
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">{editing ? 'Редактировать камеру' : 'Новая камера'}</h3>
            <button onClick={closeForm} className="text-gray-400 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="space-y-3">
            <FormField label="Путь к видео *" value={form.video_path} onChange={(v) => setForm({ ...form, video_path: v })} placeholder="/path/to/video.mp4" />
            <FormField label="Путь к изображению *" value={form.clear_image_path} onChange={(v) => setForm({ ...form, clear_image_path: v })} placeholder="/path/to/image.jpg" />
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Конфигурация сегментов *</label>
              <select
                value={form.segments_config_id}
                onChange={(e) => setForm({ ...form, segments_config_id: e.target.value })}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Выберите конфигурацию</option>
                {configsList.map((c) => (
                  <option key={c.id} value={c.id}>{c.name} ({c.horizontal_segments}×{c.vertical_segments})</option>
                ))}
              </select>
            </div>
            <div className="flex justify-end space-x-2 pt-1">
              <button onClick={closeForm} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50">Отмена</button>
              <button
                onClick={() => saveMutation.mutate(form)}
                disabled={!form.video_path || !form.clear_image_path || !form.segments_config_id}
                className="flex items-center space-x-1 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Check className="w-4 h-4" />
                <span>{editing ? 'Обновить' : 'Создать'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading ? (
        <LoadingState text="Загрузка камер..." />
      ) : camerasList.length === 0 ? (
        <EmptyState icon={Camera} title="Нет камер" description="Добавьте первую камеру для начала работы" />
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {camerasList.map((camera) => {
            const config = configsList.find((c) => c.id === camera.segments_config_id);
            return (
              <div key={camera.id} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center space-x-2">
                    <div className="w-9 h-9 bg-blue-50 rounded-lg flex items-center justify-center">
                      <Camera className="w-5 h-5 text-blue-600" />
                    </div>
                    <div>
                      <p className="font-semibold text-gray-900">Камера {camera.id}</p>
                      {config && <span className="text-xs text-blue-600 bg-blue-50 px-2 py-0.5 rounded-full">{config.name}</span>}
                    </div>
                  </div>
                  <div className="flex space-x-1">
                    <button onClick={() => openForm(camera)} className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors">
                      <Pencil className="w-3.5 h-3.5" />
                    </button>
                    <button onClick={() => { if (confirm('Удалить камеру?')) deleteMutation.mutate(camera.id); }} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                <div className="space-y-1.5 text-xs text-gray-500">
                  <p className="truncate" title={camera.video_path}><span className="font-medium text-gray-700">Видео:</span> {camera.video_path.split('/').pop()}</p>
                  <p className="truncate" title={camera.clear_image_path}><span className="font-medium text-gray-700">Изображение:</span> {camera.clear_image_path.split('/').pop()}</p>
                  {config && <p><span className="font-medium text-gray-700">Сегменты:</span> {config.horizontal_segments}×{config.vertical_segments}</p>}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ─── Configs Manager ──────────────────────────────────────────────────────────
function ConfigsManager() {
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<SegmentsConfig | null>(null);
  const [form, setForm] = useState({ name: '', horizontal_segments: 4, vertical_segments: 3, description: '' });
  const qc = useQueryClient();

  const { data: configs, isLoading } = useQuery({
    queryKey: ['segmentsConfigs'],
    queryFn: () => segmentsConfigAPI.getAll(),
    retry: false,
  });

  const saveMutation = useMutation({
    mutationFn: (data: typeof form) => editing ? segmentsConfigAPI.update(editing.id, data) : segmentsConfigAPI.create(data),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['segmentsConfigs'] }); closeForm(); },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => segmentsConfigAPI.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['segmentsConfigs'] }),
  });

  const openForm = (config?: SegmentsConfig) => {
    if (config) {
      setEditing(config);
      setForm({ name: config.name, horizontal_segments: config.horizontal_segments, vertical_segments: config.vertical_segments, description: config.description ?? '' });
    } else {
      setEditing(null);
      setForm({ name: '', horizontal_segments: 4, vertical_segments: 3, description: '' });
    }
    setShowForm(true);
  };

  const closeForm = () => { setShowForm(false); setEditing(null); };
  const configsList: SegmentsConfig[] = configs?.data?.data ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Конфигурации сегментов</h2>
          <p className="text-sm text-gray-500 mt-0.5">Настройка разметки сегментов для камер</p>
        </div>
        <button onClick={() => openForm()} className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 transition-colors">
          <Plus className="w-4 h-4" />
          <span>Добавить конфигурацию</span>
        </button>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">{editing ? 'Редактировать конфигурацию' : 'Новая конфигурация'}</h3>
            <button onClick={closeForm} className="text-gray-400 hover:text-gray-600"><X className="w-4 h-4" /></button>
          </div>
          <div className="space-y-3">
            <FormField label="Название *" value={form.name} onChange={(v) => setForm({ ...form, name: v })} placeholder="Например: 4×3 стандарт" />
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Горизонтальные сегменты *</label>
                <input type="number" min={1} max={50} value={form.horizontal_segments} onChange={(e) => setForm({ ...form, horizontal_segments: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Вертикальные сегменты *</label>
                <input type="number" min={1} max={50} value={form.vertical_segments} onChange={(e) => setForm({ ...form, vertical_segments: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Описание</label>
              <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} placeholder="Необязательное описание..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" />
            </div>
            <div className="flex justify-end space-x-2 pt-1">
              <button onClick={closeForm} className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50">Отмена</button>
              <button onClick={() => saveMutation.mutate(form)} disabled={!form.name} className="flex items-center space-x-1 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">
                <Check className="w-4 h-4" />
                <span>{editing ? 'Обновить' : 'Создать'}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {isLoading ? (
        <LoadingState text="Загрузка конфигураций..." />
      ) : configsList.length === 0 ? (
        <EmptyState icon={Settings} title="Нет конфигураций" description="Создайте первую конфигурацию сегментов" />
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-4 py-3 text-left font-medium text-gray-600">ID</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Название</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Сегменты</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Описание</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Создано</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {configsList.map((config) => (
                <tr key={config.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-500">{config.id}</td>
                  <td className="px-4 py-3 font-medium text-gray-900">{config.name}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 bg-blue-50 text-blue-700 text-xs font-medium rounded-full border border-blue-100">
                      {config.horizontal_segments}×{config.vertical_segments}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-gray-500">{config.description || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{new Date(config.created_at).toLocaleDateString('ru-RU')}</td>
                  <td className="px-4 py-3 text-right">
                    <div className="flex justify-end space-x-1">
                      <button onClick={() => openForm(config)} className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"><Pencil className="w-3.5 h-3.5" /></button>
                      <button onClick={() => { if (confirm(`Удалить конфигурацию "${config.name}"?`)) deleteMutation.mutate(config.id); }} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"><Trash2 className="w-3.5 h-3.5" /></button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Connections Manager ──────────────────────────────────────────────────────
function ConnectionsManager() {
  const { data: connections, isLoading } = useQuery({
    queryKey: ['connections'],
    queryFn: () => connectionsAPI.getAll(),
    retry: false,
  });

  const { data: cameras } = useQuery({ queryKey: ['cameras'], queryFn: () => camerasAPI.getAll(), retry: false });
  const qc = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: (id: number) => connectionsAPI.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['connections'] }),
  });

  const connectionsList = connections?.data?.data ?? [];
  const camerasList: CameraType[] = cameras?.data?.data ?? [];

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-xl font-semibold text-gray-900">Подключения камер</h2>
        <p className="text-sm text-gray-500 mt-0.5">Управление связями между сегментами камер</p>
      </div>

      {isLoading ? (
        <LoadingState text="Загрузка подключений..." />
      ) : connectionsList.length === 0 ? (
        <EmptyState icon={Link} title="Нет подключений" description="Подключения создаются через API или внешние инструменты" />
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200">
                <th className="px-4 py-3 text-left font-medium text-gray-600">ID</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Источник</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Тип</th>
                <th className="px-4 py-3 text-left font-medium text-gray-600">Назначение</th>
                <th className="px-4 py-3 text-right font-medium text-gray-600">Действия</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {connectionsList.map((conn: any) => (
                <tr key={conn.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-500">{conn.id}</td>
                  <td className="px-4 py-3">
                    <span className="font-medium text-gray-900">Камера {conn.source_camera_id}</span>
                    <span className="text-gray-400"> › </span>
                    <span className="text-blue-600 font-mono text-xs">{conn.source_segment}</span>
                  </td>
                  <td className="px-4 py-3">
                    {conn.bidirectional ? (
                      <span className="px-2 py-0.5 bg-green-50 text-green-700 text-xs font-medium rounded-full">двунаправленное</span>
                    ) : (
                      <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs font-medium rounded-full">однонаправленное</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-medium text-gray-900">Камера {conn.target_camera_id}</span>
                    <span className="text-gray-400"> › </span>
                    <span className="text-blue-600 font-mono text-xs">{conn.target_segment}</span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button onClick={() => { if (confirm('Удалить подключение?')) deleteMutation.mutate(conn.id); }} className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors">
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ─── Shared UI helpers ────────────────────────────────────────────────────────
function FormField({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
      />
    </div>
  );
}

function LoadingState({ text }: { text: string }) {
  return (
    <div className="flex items-center justify-center py-16 text-gray-400">
      <div className="text-center">
        <div className="w-8 h-8 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin mx-auto mb-3" />
        <p className="text-sm">{text}</p>
      </div>
    </div>
  );
}

function EmptyState({ icon: Icon, title, description }: { icon: React.ElementType; title: string; description: string }) {
  return (
    <div className="flex items-center justify-center py-16">
      <div className="text-center">
        <div className="w-12 h-12 bg-gray-100 rounded-xl flex items-center justify-center mx-auto mb-3">
          <Icon className="w-6 h-6 text-gray-400" />
        </div>
        <p className="font-medium text-gray-700">{title}</p>
        <p className="text-sm text-gray-400 mt-1">{description}</p>
      </div>
    </div>
  );
}
