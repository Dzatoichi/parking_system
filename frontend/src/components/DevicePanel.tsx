import React, { useEffect, useState } from "react";
import { Card } from "./ui/card";
import { Button } from "./ui/button";
import { DeviceApi, type DeviceStateOut, type CommandResultOut } from "../services/pmApi";
import { useActiveParking } from "../hooks/useActiveParking";

type LogEntry = {
  id: number;
  time: string;
  message: string;
  success: boolean;
};

export function DevicePanel() {
  const parkingQuery = useActiveParking();
  const parkingId = parkingQuery.data?.id ?? null;

  const [state, setState] = useState<DeviceStateOut | null>(null);
  const [loadingState, setLoadingState] = useState(false);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const [logCounter, setLogCounter] = useState(0);
  const [simulateUnreachable, setSimulateUnreachable] = useState(false);

  const addLog = (message: string, success: boolean) => {
    const entry: LogEntry = {
      id: logCounter,
      time: new Date().toLocaleTimeString("ru-RU"),
      message,
      success,
    };
    setLogCounter((c) => c + 1);
    setLog((prev) => [entry, ...prev].slice(0, 20)); // хранить последние 20
  };

  const fetchState = async () => {
    if (!parkingId) return;
    setLoadingState(true);
    try {
      const res = await DeviceApi.getDevicesState(parkingId);
      setState(res.data);
    } catch {
      addLog("Ошибка получения состояния устройств", false);
    } finally {
      setLoadingState(false);
    }
  };

  // Polling каждые 5 секунд
  useEffect(() => {
    if (!parkingId) return;
    fetchState();
    const interval = setInterval(fetchState, 5000);
    return () => clearInterval(interval);
  }, [parkingId]);

  const handleCommand = async (
    label: string,
    fn: () => Promise<{ data: CommandResultOut }>
  ) => {
    setActionLoading(label);
    try {
      const res = await fn();
      const result = res.data;
      addLog(
        `${label}: ${result.message ?? (result.success ? "успешно" : "ошибка")}`,
        result.success
      );
      // Обновить состояние после команды
      await fetchState();
    } catch {
      addLog(`${label}: не удалось выполнить команду`, false);
      if (simulateUnreachable) {
        addLog("Устройство недоступно (симуляция)", false);
      }
    } finally {
      setActionLoading(null);
    }
  };

  if (!parkingId) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-semibold text-gray-900">Управление устройствами</h1>
        <p className="text-gray-500">Нет активной парковки</p>
      </div>
    );
  }

  const barrierOpen = state?.barrier.position === "open";
  const lightingOn = state?.lighting.on ?? false;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-gray-900">Управление устройствами</h1>
          <p className="text-gray-500 text-sm mt-1">
            Парковка #{parkingId}
          </p>
        </div>
        <Button
          variant="outline"
          onClick={fetchState}
          disabled={loadingState}
          className="text-sm"
        >
          {loadingState ? "Обновление..." : "Обновить"}
        </Button>
      </div>

      <div className="grid grid-cols-3 gap-6">

        {/* Шлагбаум */}
        <Card className="p-6 bg-white shadow-sm space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">Шлагбаум</h3>
            {state ? (
              <span
                className={`text-xs font-medium px-2 py-1 rounded-full ${
                  barrierOpen
                    ? "bg-green-100 text-green-700"
                    : "bg-gray-100 text-gray-600"
                }`}
              >
                {barrierOpen ? "Открыт" : "Закрыт"}
              </span>
            ) : (
              <span className="text-xs text-gray-400">—</span>
            )}
          </div>

          {/* Визуальный индикатор */}
          <div className="flex items-center justify-center h-20">
            <div className="relative flex items-end justify-center w-32 h-16">
              {/* Стойка */}
              <div className="absolute left-4 bottom-0 w-2 h-16 bg-gray-400 rounded" />
              {/* Перекладина */}
              <div
                className={`absolute left-6 bottom-14 h-2 w-24 rounded transition-all duration-700 origin-left ${
                  barrierOpen
                    ? "bg-green-500 rotate-[-90deg] translate-x-0 translate-y-12"
                    : "bg-red-500 rotate-0"
                }`}
              />
            </div>
          </div>

          <div className="flex gap-2">
            <Button
              className="flex-1 bg-green-600 hover:bg-green-700 text-white text-sm"
              disabled={actionLoading !== null || barrierOpen}
              onClick={() =>
                handleCommand("Открыть шлагбаум", () =>
                  DeviceApi.openBarrier({
                    parkingId,
                    simulate_unreachable: simulateUnreachable,
                  })
                )
              }
            >
              {actionLoading === "Открыть шлагбаум" ? "..." : "Открыть"}
            </Button>
            <Button
              className="flex-1 bg-red-600 hover:bg-red-700 text-white text-sm"
              disabled={actionLoading !== null || !barrierOpen}
              onClick={() =>
                handleCommand("Закрыть шлагбаум", () =>
                  DeviceApi.closeBarrier({
                    parkingId,
                    simulate_unreachable: simulateUnreachable,
                  })
                )
              }
            >
              {actionLoading === "Закрыть шлагбаум" ? "..." : "Закрыть"}
            </Button>
          </div>
        </Card>

        {/* Освещение */}
        <Card className="p-6 bg-white shadow-sm">
        <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Освещение</h3>
            {state ? (
            <span className={`text-xs font-medium px-2 py-1 rounded-full ${
                lightingOn ? "bg-yellow-100 text-yellow-700" : "bg-gray-100 text-gray-600"
            }`}>
                {lightingOn ? "Включено" : "Выключено"}
            </span>
            ) : (
            <span className="text-xs text-gray-400">—</span>
            )}
        </div>

        <div className="flex items-center justify-center h-20 mb-4">
            <div className={`text-6xl transition-all duration-300 ${lightingOn ? "opacity-100" : "opacity-20"}`}>
            💡
            </div>
        </div>

        <Button
            className={`w-full text-sm ${
            lightingOn
                ? "bg-gray-200 hover:bg-gray-300 text-gray-800"
                : "bg-yellow-400 hover:bg-yellow-500 text-gray-900"
            }`}
            disabled={actionLoading !== null}
            onClick={() =>
            handleCommand(
                lightingOn ? "Выключить свет" : "Включить свет",
                () => DeviceApi.setLighting({
                parkignId: parkingId,
                body: {
                    on: !lightingOn,
                    brightness: lightingOn ? 0 : 100,
                    simulate_unreachable: simulateUnreachable,
                },
                })
            )
            }
        >
            {actionLoading === "Включить свет" || actionLoading === "Выключить свет"
            ? "..."
            : lightingOn ? "Выключить" : "Включить"}
        </Button>
        </Card>

        {/* Симуляция и настройки */}
        <Card className="p-6 bg-white shadow-sm">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Симуляция</h3>

        <div
            className="flex items-center justify-between p-3 rounded-lg border border-gray-200 mb-3"
            onClick={() => setSimulateUnreachable((v) => !v)}
            style={{ cursor: "pointer" }}
        >
            <div>
            <p className="text-sm font-medium text-gray-700">
                Симулировать недоступность
            </p>
            <p className="text-xs text-gray-400 mt-0.5">
                Следующие команды вернут ошибку
            </p>
            </div>
            <div
            className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-200 ${
                simulateUnreachable ? "bg-red-500" : "bg-gray-300"
            }`}
            >
            <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform duration-200 ${
                simulateUnreachable ? "translate-x-6" : "translate-x-1"
                }`}
            />
            </div>
        </div>

        {simulateUnreachable && (
            <div className="text-xs text-red-600 bg-red-50 border border-red-200 rounded p-2 mb-3">
            ⚠ Режим симуляции недоступности активен
            </div>
        )}

        {state && (
            <div className="rounded-lg bg-gray-50 border border-gray-100 p-3 space-y-1">
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-1">
                Состояние устройств
            </p>
            <p className="text-xs text-gray-600">
                Шлагбаум: <span className="font-medium">{state.barrier.position}</span>
            </p>
            <p className="text-xs text-gray-600">
                Свет: <span className="font-medium">{state.lighting.on ? "on" : "off"}</span>
                {" "}/ яркость{" "}
                <span className="font-medium">{state.lighting.brightness}%</span>
            </p>
            </div>
        )}
        </Card>
      </div>

      {/* Журнал команд */}
      <Card className="p-6 bg-white shadow-sm">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          Журнал команд
        </h3>
        {log.length === 0 ? (
          <p className="text-sm text-gray-400">Команды ещё не выполнялись</p>
        ) : (
          <div className="space-y-2 max-h-48 overflow-y-auto">
            {log.map((entry) => (
              <div
                key={entry.id}
                className="flex items-start gap-3 py-2 border-b border-gray-50 last:border-0"
              >
                <span className="text-xs text-gray-400 w-16 shrink-0 pt-0.5">
                  {entry.time}
                </span>
                <span
                  className={`text-xs font-medium shrink-0 pt-0.5 ${
                    entry.success ? "text-green-600" : "text-red-500"
                  }`}
                >
                  {entry.success ? "✓" : "✗"}
                </span>
                <span className="text-sm text-gray-700">{entry.message}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}