import React, { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Camera,
  Check,
  LayoutDashboard,
  MousePointer2,
  Pencil,
  Play,
  Plus,
  Square,
  Trash2,
  X,
} from "lucide-react";
import {
  cameraApi,
  cvMonitoringApi,
  parkingApi,
  type CameraRead,
  type ParkingRead,
} from "../../services/pmApi";
import { getApiErrorMessage } from "../../lib/api";

type CameraView = "dashboard" | "cameras";

export function CameraNetwork() {
  const [activeView, setActiveView] = useState<CameraView>("dashboard");

  const views = [
    { id: "dashboard" as CameraView, label: "Панель", icon: LayoutDashboard },
    { id: "cameras" as CameraView, label: "Камеры", icon: Camera },
  ];

  return (
    <div className="flex flex-col h-full">
      <div className="bg-white border-b border-gray-200 px-6">
        <div className="flex items-center space-x-1">
          <div className="flex items-center space-x-2 py-3 pr-6 border-r border-gray-200 mr-2">
            <div className="w-7 h-7 bg-blue-600 rounded-md flex items-center justify-center">
              <Camera className="w-4 h-4 text-white" />
            </div>
            <span className="font-semibold text-gray-900 text-sm">
              Настройка камер
            </span>
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
                    ? "border-blue-600 text-blue-600"
                    : "border-transparent text-gray-600 hover:text-gray-900 hover:border-gray-300"
                }`}
              >
                <Icon className="w-4 h-4" />
                <span>{view.label}</span>
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex-1 overflow-auto p-6">
        {activeView === "dashboard" && <CamerasDashboard />}
        {activeView === "cameras" && <CamerasManager />}
      </div>
    </div>
  );
}

function CamerasDashboard() {
  const qc = useQueryClient();
  const [monitorActionError, setMonitorActionError] = useState<string | null>(null);
  const { data: parkingsResp } = useQuery({
    queryKey: ["parkings"],
    queryFn: () => parkingApi.getAll({ page: 1, size: 200 }),
    retry: false,
  });
  const { data: monitoringResp, error: monitoringError, isLoading: monitoringLoading } = useQuery({
    queryKey: ["cvMonitoringStatus"],
    queryFn: () => cvMonitoringApi.getStatus(),
    refetchInterval: 5000,
    retry: false,
  });

  const parkings = parkingsResp?.data?.items ?? [];
  const monitoring = monitoringResp?.data;
  const refreshMonitoring = () => {
    setMonitorActionError(null);
    return qc.invalidateQueries({ queryKey: ["cvMonitoringStatus"] });
  };
  const showMonitorError = (error: unknown) => {
    setMonitorActionError(getApiErrorMessage(error, "Не удалось выполнить команду CV-мониторинга"));
  };
  const startMonitoring = useMutation({
    mutationFn: () => cvMonitoringApi.start(),
    onSuccess: refreshMonitoring,
    onError: showMonitorError,
  });
  const stopMonitoring = useMutation({
    mutationFn: () => cvMonitoringApi.stop(),
    onSuccess: refreshMonitoring,
    onError: showMonitorError,
  });
  const beginMarkup = useMutation({
    mutationFn: () => cvMonitoringApi.beginMarkup(),
    onSuccess: refreshMonitoring,
    onError: showMonitorError,
  });
  const finishMarkup = useMutation({
    mutationFn: () => cvMonitoringApi.finishMarkup(),
    onSuccess: refreshMonitoring,
    onError: showMonitorError,
  });
  const monitorErrorText =
    monitorActionError || getApiErrorMessage(monitoringError, "");
  const monitorBusy =
    startMonitoring.isPending ||
    stopMonitoring.isPending ||
    beginMarkup.isPending ||
    finishMarkup.isPending;

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">
          Панель управления
        </h2>
        <p className="text-sm text-gray-500 mt-1">
          Камеры в разрезе парковок
        </p>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm text-gray-500">CV мониторинг</p>
            <p className="text-lg font-semibold text-gray-900 mt-1">
              {monitoringLoading ? "Проверка..." : monitoring?.mode ?? "offline"}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              Камер: {monitoring?.monitor?.cameras ?? 0}, активных процессоров:{" "}
              {monitoring?.monitor?.active_processors ?? 0}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => startMonitoring.mutate()}
              disabled={monitorBusy || monitoring?.mode === "markup" || monitoring?.running}
              className="flex items-center gap-2 px-3 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50"
            >
              <Play className="w-4 h-4" />
              <span>Старт</span>
            </button>
            <button
              onClick={() => stopMonitoring.mutate()}
              disabled={monitorBusy || !monitoring?.running}
              className="flex items-center gap-2 px-3 py-2 bg-gray-900 text-white text-sm font-medium rounded-lg hover:bg-black disabled:opacity-50"
            >
              <Square className="w-4 h-4" />
              <span>Стоп</span>
            </button>
            <button
              onClick={() => beginMarkup.mutate()}
              disabled={monitorBusy || monitoring?.running || monitoring?.mode === "markup"}
              className="flex items-center gap-2 px-3 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              <MousePointer2 className="w-4 h-4" />
              <span>Разметка</span>
            </button>
            <button
              onClick={() => finishMarkup.mutate()}
              disabled={monitorBusy || monitoring?.mode !== "markup"}
              className="px-3 py-2 border border-gray-300 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-50 disabled:opacity-50"
            >
              Готово
            </button>
          </div>
        </div>
        {monitorErrorText && (
          <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
            {monitorErrorText}
          </div>
        )}
      </div>

      {parkings.length === 0 ? (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 flex items-start space-x-3">
          <AlertCircle className="w-5 h-5 text-blue-600 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-medium text-blue-800">
              Нет парковок
            </p>
            <p className="text-sm text-blue-700 mt-1">
              Сначала создайте парковку, затем добавьте камеры.
            </p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {parkings.map((p) => (
            <ParkingCamerasStatCard key={p.id} parking={p} />
          ))}
        </div>
      )}
    </div>
  );
}

function ParkingCamerasStatCard({ parking }: { parking: ParkingRead }) {
  const { data } = useQuery({
    queryKey: ["camerasByParking", parking.id],
    queryFn: () => cameraApi.getByParking(parking.id),
    retry: false,
  });

  const total = data?.data?.total ?? 0;

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
      <p className="text-sm text-gray-500">Парковка</p>
      <p className="text-lg font-semibold text-gray-900 mt-1">{parking.name}</p>
      <p className="text-xs text-gray-500 mt-1 truncate" title={parking.address}>
        {parking.address}
      </p>
      <div className="mt-4 flex items-center justify-between">
        <p className="text-sm text-gray-500">Камер</p>
        <p className="text-2xl font-bold text-gray-900">{total}</p>
      </div>
    </div>
  );
}

function CamerasManager() {
  const qc = useQueryClient();
  const [parkingId, setParkingId] = useState<number | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<CameraRead | null>(null);
  const [form, setForm] = useState({
    rtsp_url: "",
    position_x: "",
    position_y: "",
    is_calibrated: false,
  });

  const { data: parkingsResp, isLoading: parkingsLoading } = useQuery({
    queryKey: ["parkings"],
    queryFn: () => parkingApi.getAll({ page: 1, size: 200 }),
    retry: false,
  });

  const parkings = parkingsResp?.data?.items ?? [];

  const effectiveParkingId = useMemo(() => {
    if (parkingId != null) return parkingId;
    return parkings[0]?.id ?? null;
  }, [parkingId, parkings]);

  const { data: camerasResp, isLoading: camerasLoading } = useQuery({
    queryKey: ["camerasByParking", effectiveParkingId],
    queryFn: () => cameraApi.getByParking(effectiveParkingId as number),
    enabled: effectiveParkingId != null,
    retry: false,
  });

  const cameras = camerasResp?.data?.cameras ?? [];

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        rtsp_url: form.rtsp_url,
        position_x: form.position_x === "" ? null : Number(form.position_x),
        position_y: form.position_y === "" ? null : Number(form.position_y),
        is_calibrated: form.is_calibrated,
      };
      if (editing) return cameraApi.update(editing.id, payload);
      return cameraApi.create(effectiveParkingId as number, payload);
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["camerasByParking", effectiveParkingId] });
      closeForm();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => cameraApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["camerasByParking", effectiveParkingId] }),
  });

  const openForm = (camera?: CameraRead) => {
    if (camera) {
      setEditing(camera);
      setForm({
        rtsp_url: camera.rtsp_url,
        position_x: camera.position_x == null ? "" : String(camera.position_x),
        position_y: camera.position_y == null ? "" : String(camera.position_y),
        is_calibrated: camera.is_calibrated,
      });
    } else {
      setEditing(null);
      setForm({ rtsp_url: "", position_x: "", position_y: "", is_calibrated: false });
    }
    setShowForm(true);
  };

  const closeForm = () => {
    setShowForm(false);
    setEditing(null);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-gray-900">Камеры</h2>
          <p className="text-sm text-gray-500 mt-0.5">
            Добавление и настройка камер парковки
          </p>
        </div>
        <button
          onClick={() => openForm()}
          disabled={effectiveParkingId == null}
          className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Добавить камеру</span>
        </button>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
        <label className="block text-sm font-medium text-gray-700 mb-1">
          Парковка
        </label>
        <select
          value={effectiveParkingId ?? ""}
          disabled={parkingsLoading || parkings.length === 0}
          onChange={(e) => setParkingId(Number(e.target.value))}
          className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          {parkings.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      {showForm && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">
              {editing ? "Редактировать камеру" : "Новая камера"}
            </h3>
            <button onClick={closeForm} className="text-gray-400 hover:text-gray-600">
              <X className="w-4 h-4" />
            </button>
          </div>
          <div className="space-y-3">
            <FormField
              label="RTSP URL *"
              value={form.rtsp_url}
              onChange={(v) => setForm({ ...form, rtsp_url: v })}
              placeholder="rtsp://..."
            />
            <div className="grid grid-cols-2 gap-3">
              <FormField
                label="position_x"
                value={form.position_x}
                onChange={(v) => setForm({ ...form, position_x: v })}
                placeholder="например 120"
              />
              <FormField
                label="position_y"
                value={form.position_y}
                onChange={(v) => setForm({ ...form, position_y: v })}
                placeholder="например 340"
              />
            </div>
            <label className="flex items-center space-x-2 text-sm text-gray-700">
              <input
                type="checkbox"
                checked={form.is_calibrated}
                onChange={(e) =>
                  setForm({ ...form, is_calibrated: e.target.checked })
                }
              />
              <span>Камера откалибрована</span>
            </label>
            <div className="flex justify-end space-x-2 pt-1">
              <button
                onClick={closeForm}
                className="px-4 py-2 text-sm text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Отмена
              </button>
              <button
                onClick={() => saveMutation.mutate()}
                disabled={!form.rtsp_url}
                className="flex items-center space-x-1 px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                <Check className="w-4 h-4" />
                <span>{editing ? "Обновить" : "Создать"}</span>
              </button>
            </div>
          </div>
        </div>
      )}

      {camerasLoading ? (
        <LoadingState text="Загрузка камер..." />
      ) : cameras.length === 0 ? (
        <EmptyState icon={Camera} title="Нет камер" description="Добавьте первую камеру" />
      ) : (
        <div className="grid grid-cols-2 gap-4">
          {cameras.map((camera) => (
            <div key={camera.id} className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
              <div className="flex items-start justify-between mb-2">
                <div className="flex items-center space-x-2">
                  <div className="w-9 h-9 bg-blue-50 rounded-lg flex items-center justify-center">
                    <Camera className="w-5 h-5 text-blue-600" />
                  </div>
                  <div>
                    <p className="font-semibold text-gray-900">Камера {camera.id}</p>
                    <p className="text-xs text-gray-500">{camera.status}</p>
                  </div>
                </div>
                <div className="flex space-x-1">
                  <button onClick={() => openForm(camera)} className="p-1.5 text-gray-400 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors">
                    <Pencil className="w-3.5 h-3.5" />
                  </button>
                  <button
                    onClick={() => {
                      if (confirm("Удалить камеру?")) deleteMutation.mutate(camera.id);
                    }}
                    className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <div className="text-xs text-gray-500 space-y-1">
                <p className="truncate" title={camera.rtsp_url}>
                  <span className="font-medium text-gray-700">RTSP:</span>{" "}
                  {camera.rtsp_url}
                </p>
                <p>
                  <span className="font-medium text-gray-700">Позиция:</span>{" "}
                  {camera.position_x ?? "—"} / {camera.position_y ?? "—"}
                </p>
                <p>
                  <span className="font-medium text-gray-700">Калибровка:</span>{" "}
                  {camera.is_calibrated ? "да" : "нет"}
                </p>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function FormField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
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
