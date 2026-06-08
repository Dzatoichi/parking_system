import React, { useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Maximize2, Pencil, Plus, RefreshCw, RotateCw, Save, Trash2 } from "lucide-react";

import {
  cvMonitoringApi,
  type ParkingScene,
  type ParkingSceneContainer,
  type ParkingScenesResponse,
  type ParkingSceneVehicle,
} from "../services/pmApi";
import { getApiErrorMessage } from "../lib/api";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "./ui/select";

type WidgetLayout = {
  id: number;
  cameraId: string;
  x: number;
  y: number;
  width: number;
  height: number;
  zoom: number;
  panX: number;
  panY: number;
  rotation: 0 | 90 | 180 | 270;
};

type DragState =
  | { type: "move"; id: number; startX: number; startY: number; x: number; y: number }
  | { type: "resize"; id: number; startX: number; startY: number; width: number; height: number };

const STORAGE_KEY = "cv_monitoring_map_layout_v2";
const HEADER_HEIGHT = 42;
const MIN_WIDGET_WIDTH = 320;
const MIN_WIDGET_HEIGHT = 240;
const UNASSIGNED_CAMERA_ID = "__unassigned__";

export function ParkingSceneWidget() {
  const [widgets, setWidgets] = useState<WidgetLayout[]>([]);
  const [editMode, setEditMode] = useState(false);
  const [drag, setDrag] = useState<DragState | null>(null);
  const [wsScenes, setWsScenes] = useState<Record<string, ParkingScene> | null>(null);
  const [wsError, setWsError] = useState<string | null>(null);
  const lastWsMessageRef = useRef<string>("");

  const scenesQuery = useQuery({
    queryKey: ["cvMonitoringScenes"],
    queryFn: () => cvMonitoringApi.getScenes(),
    retry: false,
  });

  useEffect(() => {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${protocol}//${window.location.host}/cv/v1/monitoring/scenes/ws`);

    ws.onmessage = (event) => {
      try {
        if (event.data === lastWsMessageRef.current) return;
        lastWsMessageRef.current = event.data;

        const payload = JSON.parse(event.data) as ParkingScenesResponse;
        if (payload.type === "all_scenes" && payload.data) {
          setWsScenes(payload.data);
          setWsError(null);
        }
      } catch {
        setWsError("Ошибка потока CV-сцен");
      }
    };

    ws.onerror = () => {
      setWsError("WebSocket CV-сцен недоступен");
    };

    return () => {
      ws.close();
    };
  }, []);

  const scenes = wsScenes ?? scenesQuery.data?.data.data ?? {};
  const cameraIds = Object.keys(scenes).sort((a, b) => Number(a) - Number(b));
  const cameraIdsKey = cameraIds.join("|");
  const firstCameraId = cameraIds[0] ?? "";
  const error = wsError || getApiErrorMessage(scenesQuery.error, "");
  const topWidgetId = widgets[0]?.id ?? null;

  useEffect(() => {
    if (widgets.length) return;

    const saved = loadSavedLayout();
    if (saved.length) {
      setWidgets(saved);
      return;
    }

    if (firstCameraId) {
      setWidgets([createWidget(1, firstCameraId, 16, 16)]);
    }
  }, [cameraIdsKey, firstCameraId, widgets.length]);

  useEffect(() => {
    if (!firstCameraId) return;

    setWidgets((current) => {
      let changed = false;
      const next = current.map((widget) => {
        if (widget.cameraId && cameraIds.includes(widget.cameraId)) return widget;
        changed = true;
        return { ...widget, cameraId: firstCameraId };
      });
      return changed ? next : current;
    });
  }, [cameraIdsKey, firstCameraId]);

  useEffect(() => {
    if (!drag) return;

    const handleMove = (event: MouseEvent) => {
      setWidgets((current) =>
        current.map((widget) => {
          if (widget.id !== drag.id) return widget;

          if (drag.type === "move") {
            return {
              ...widget,
              x: Math.max(0, drag.x + event.clientX - drag.startX),
              y: Math.max(0, drag.y + event.clientY - drag.startY),
            };
          }

          return {
            ...widget,
            width: Math.max(MIN_WIDGET_WIDTH, drag.width + event.clientX - drag.startX),
            height: Math.max(MIN_WIDGET_HEIGHT, drag.height + event.clientY - drag.startY),
          };
        }),
      );
    };

    const handleUp = () => setDrag(null);
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [drag]);

  const addWidget = () => {
    setWidgets((current) => {
      const id = Math.max(0, ...current.map((widget) => widget.id)) + 1;
      return [createWidget(id, firstCameraId || UNASSIGNED_CAMERA_ID, 24, 52), ...current];
    });
  };

  const updateWidget = (id: number, patch: Partial<WidgetLayout>) => {
    setWidgets((current) => current.map((widget) => (widget.id === id ? { ...widget, ...patch } : widget)));
  };

  const removeWidget = (id: number) => {
    setWidgets((current) => current.filter((widget) => widget.id !== id));
  };

  const saveLayout = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(widgets));
    setEditMode(false);
  };

  return (
    <Card className="bg-white p-4 shadow-sm">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">CV мониторинг</h3>
          <p className="text-sm text-gray-500">Цифровая карта из виджетов камер</p>
        </div>

        <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          Виджетов: {widgets.length}
          {topWidgetId ? `, верхний #${topWidgetId}` : ""}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" className="gap-2" onClick={() => scenesQuery.refetch()}>
            <RefreshCw className="h-4 w-4" />
            Обновить
          </Button>

          {editMode && (
            <Button
              variant="outline"
              className="gap-2"
              onPointerDown={(event) => {
                event.preventDefault();
                event.stopPropagation();
                addWidget();
              }}
              type="button"
            >
              <Plus className="h-4 w-4" />
              Виджет
            </Button>
          )}

          <Button className="gap-2" onClick={editMode ? saveLayout : () => setEditMode(true)}>
            {editMode ? <Save className="h-4 w-4" /> : <Pencil className="h-4 w-4" />}
            {editMode ? "Сохранить" : "Редактировать"}
          </Button>
        </div>
      </div>

      <div
        className="relative overflow-auto rounded-md border border-gray-200 bg-slate-100"
        style={{ height: 620, minHeight: 620 }}
      >
        {editMode && (
          <div className="pointer-events-none absolute left-3 top-3 z-30 rounded bg-white/90 px-2 py-1 text-xs text-slate-600 shadow-sm">
            Карта виджетов: {widgets.length}
          </div>
        )}
        {widgets.map((widget) => (
          <SceneWidget
            key={widget.id}
            active={widget.id === topWidgetId}
            cameraIds={cameraIds}
            editMode={editMode}
            scene={scenes[widget.cameraId]}
            widget={widget}
            onMoveStart={(event) => {
              setDrag({
                type: "move",
                id: widget.id,
                startX: event.clientX,
                startY: event.clientY,
                x: widget.x,
                y: widget.y,
              });
            }}
            onResizeStart={(event) => {
              setDrag({
                type: "resize",
                id: widget.id,
                startX: event.clientX,
                startY: event.clientY,
                width: widget.width,
                height: widget.height,
              });
            }}
            onRemove={() => removeWidget(widget.id)}
            onUpdate={(patch) => updateWidget(widget.id, patch)}
          />
        ))}

        {!widgets.length && (
          <div className="flex h-[420px] items-center justify-center text-sm text-gray-500">
            Нет виджетов мониторинга
          </div>
        )}
      </div>

      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
      {!cameraIds.length && !scenesQuery.isLoading && !error && (
        <p className="mt-3 text-sm text-gray-500">CV-сервис пока не вернул сцены камер</p>
      )}
    </Card>
  );
}

function SceneWidget({
  active,
  cameraIds,
  editMode,
  scene,
  widget,
  onMoveStart,
  onResizeStart,
  onRemove,
  onUpdate,
}: {
  active: boolean;
  cameraIds: string[];
  editMode: boolean;
  scene: ParkingScene | undefined;
  widget: WidgetLayout;
  onMoveStart: (event: React.MouseEvent) => void;
  onResizeStart: (event: React.MouseEvent) => void;
  onRemove: () => void;
  onUpdate: (patch: Partial<WidgetLayout>) => void;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [panStart, setPanStart] = useState<{ x: number; y: number; panX: number; panY: number } | null>(null);

  useAutoFit(scene, widget, canvasRef.current, onUpdate);

  useEffect(() => {
    drawScene(canvasRef.current, scene, widget);
  }, [scene, widget]);

  const widgetStyle = useMemo(
    () => ({
      left: widget.x,
      top: widget.y,
      width: widget.width,
      height: widget.height,
    }),
    [widget.height, widget.width, widget.x, widget.y],
  );

  const rotate = () => {
    onUpdate({ rotation: ((widget.rotation + 90) % 360) as WidgetLayout["rotation"] });
  };

  return (
    <div
      className={`absolute overflow-hidden rounded-md bg-white shadow-sm ${
        editMode ? (active ? "border-2 border-emerald-500" : "border-2 border-blue-400") : "border border-gray-200"
      }`}
      style={{ ...widgetStyle, zIndex: active ? 20 : widget.id }}
    >
      <div
        className={`flex h-[42px] items-center justify-between gap-2 border-b border-gray-200 px-2 ${
          editMode ? "cursor-move bg-blue-50" : "bg-white"
        }`}
        onMouseDown={(event) => {
          if (editMode) onMoveStart(event);
        }}
      >
        {editMode ? (
          <div onMouseDown={(event) => event.stopPropagation()}>
            <Select value={widget.cameraId || UNASSIGNED_CAMERA_ID} onValueChange={(cameraId) => onUpdate({ cameraId })}>
              <SelectTrigger className="h-8 w-40 bg-white">
                <SelectValue placeholder="Камера" />
              </SelectTrigger>
              <SelectContent>
                {!cameraIds.length && (
                  <SelectItem value={UNASSIGNED_CAMERA_ID} disabled>
                    Нет камер
                  </SelectItem>
                )}
                {cameraIds.map((cameraId) => (
                  <SelectItem key={cameraId} value={cameraId}>
                    Камера {cameraId}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        ) : (
          <span className="truncate text-sm font-medium text-gray-800">Камера {widget.cameraId}</span>
        )}

        <div className="flex items-center gap-1">
          <span className="rounded border border-gray-200 bg-white px-2 py-1 text-xs text-gray-500">
            {widget.rotation}°
          </span>

          {editMode && (
            <>
              <Button
                size="icon"
                variant="ghost"
                title="Повернуть вид"
                onMouseDown={(event) => event.stopPropagation()}
                onClick={rotate}
              >
                <RotateCw className="h-4 w-4" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                title="Удалить виджет"
                onMouseDown={(event) => event.stopPropagation()}
                onClick={onRemove}
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            </>
          )}
        </div>
      </div>

      <canvas
        ref={canvasRef}
        width={Math.max(1, widget.width)}
        height={Math.max(1, widget.height - HEADER_HEIGHT)}
        className={editMode ? "block cursor-default bg-slate-950" : "block cursor-grab bg-slate-950 active:cursor-grabbing"}
        style={{ width: "100%", height: widget.height - HEADER_HEIGHT }}
        onMouseDown={(event) => {
          if (editMode) return;
          setPanStart({ x: event.clientX, y: event.clientY, panX: widget.panX, panY: widget.panY });
        }}
        onMouseMove={(event) => {
          if (editMode || !panStart) return;
          onUpdate({
            panX: panStart.panX + event.clientX - panStart.x,
            panY: panStart.panY + event.clientY - panStart.y,
          });
        }}
        onMouseUp={() => setPanStart(null)}
        onMouseLeave={() => setPanStart(null)}
        onWheel={(event) => {
          if (editMode) return;
          event.preventDefault();
          const factor = event.deltaY < 0 ? 1.12 : 1 / 1.12;
          onUpdate({ zoom: clamp(widget.zoom * factor, 0.05, 80) });
        }}
      />

        {!scene && (
          <div className="pointer-events-none absolute inset-x-0 top-[42px] flex h-[calc(100%-42px)] items-center justify-center text-sm text-slate-300">
            {cameraIds.length ? "Выберите камеру" : "CV-сцены не загружены"}
          </div>
        )}

      {editMode && (
        <button
          className="absolute bottom-0 right-0 flex h-7 w-7 cursor-nwse-resize items-center justify-center bg-blue-600 text-white"
          onMouseDown={(event) => {
            event.stopPropagation();
            onResizeStart(event);
          }}
          type="button"
          title="Изменить размер"
        >
          <Maximize2 className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

function createWidget(id: number, cameraId: string, x: number, y: number): WidgetLayout {
  return {
    id,
    cameraId,
    x,
    y,
    width: 460,
    height: 340,
    zoom: 1,
    panX: 0,
    panY: 0,
    rotation: 0,
  };
}

function loadSavedLayout(): WidgetLayout[] {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (!saved) return [];

    const parsed = JSON.parse(saved) as WidgetLayout[];
    if (!Array.isArray(parsed)) return [];

    return parsed
      .filter((widget) => typeof widget.id === "number")
      .map((widget) => ({
        ...createWidget(widget.id, widget.cameraId ?? "", widget.x ?? 0, widget.y ?? 0),
        ...widget,
        width: Math.max(MIN_WIDGET_WIDTH, widget.width ?? MIN_WIDGET_WIDTH),
        height: Math.max(MIN_WIDGET_HEIGHT, widget.height ?? MIN_WIDGET_HEIGHT),
        rotation: normalizeRotation(widget.rotation),
      }));
  } catch {
    return [];
  }
}

function useAutoFit(
  scene: ParkingScene | undefined,
  widget: WidgetLayout,
  canvas: HTMLCanvasElement | null,
  onUpdate: (patch: Partial<WidgetLayout>) => void,
) {
  const fitKey = `${widget.cameraId}:${widget.width}:${widget.height}:${widget.rotation}:${scene?.bbox?.join(",") ?? ""}`;

  useEffect(() => {
    if (!scene || !canvas) return;

    const bbox = getSceneBbox(scene);
    const width = Math.max(bbox.maxX - bbox.minX, 1);
    const height = Math.max(bbox.maxZ - bbox.minZ, 1);
    const zoom = Math.max(0.05, Math.min((canvas.width - 56) / width, (canvas.height - 56) / height));

    onUpdate({
      zoom,
      panX: 0,
      panY: 0,
    });
  }, [fitKey]);
}

function drawScene(canvas: HTMLCanvasElement | null, scene: ParkingScene | undefined, widget: WidgetLayout) {
  if (!canvas) return;

  const ctx = canvas.getContext("2d");
  if (!ctx) return;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#020617";
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  const bbox = getSceneBbox(scene);
  drawGrid(ctx, canvas, widget, bbox);

  const containers = scene?.containers?.length ? scene.containers : scene?.spots ?? [];
  for (const container of containers) {
    drawContainer(ctx, canvas, widget, bbox, container);
  }

  for (const vehicle of scene?.vehicles ?? []) {
    drawVehicle(ctx, canvas, widget, bbox, vehicle);
  }

  drawLegend(ctx, canvas, scene);
}

function drawGrid(ctx: CanvasRenderingContext2D, canvas: HTMLCanvasElement, widget: WidgetLayout, bbox: SceneBbox) {
  const startX = Math.floor((bbox.minX - 10) / 5) * 5;
  const endX = Math.ceil((bbox.maxX + 10) / 5) * 5;
  const startZ = Math.floor((bbox.minZ - 10) / 5) * 5;
  const endZ = Math.ceil((bbox.maxZ + 10) / 5) * 5;

  ctx.strokeStyle = "#1e293b";
  ctx.lineWidth = 1;

  for (let x = startX; x <= endX; x += 5) {
    const a = worldToScreen(canvas, widget, bbox, x, startZ);
    const b = worldToScreen(canvas, widget, bbox, x, endZ);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }

  for (let z = startZ; z <= endZ; z += 5) {
    const a = worldToScreen(canvas, widget, bbox, startX, z);
    const b = worldToScreen(canvas, widget, bbox, endX, z);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }
}

function drawContainer(
  ctx: CanvasRenderingContext2D,
  canvas: HTMLCanvasElement,
  widget: WidgetLayout,
  bbox: SceneBbox,
  container: ParkingSceneContainer,
) {
  const points = container.ground_points.map((point) => worldToScreen(canvas, widget, bbox, point[0], point[2]));
  if (points.length < 3) return;

  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  points.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
  ctx.closePath();

  ctx.fillStyle = container.occupied ? "rgba(239, 68, 68, 0.58)" : "rgba(34, 197, 94, 0.46)";
  ctx.strokeStyle = container.occupied ? "#fecaca" : "#bbf7d0";
  ctx.lineWidth = 1.6;
  ctx.fill();
  ctx.stroke();

  const center = average(points);
  ctx.fillStyle = "#f8fafc";
  ctx.font = "600 12px Inter, Arial";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(container.name || String(container.spot_id ?? container.id), center.x, center.y);
}

function drawVehicle(
  ctx: CanvasRenderingContext2D,
  canvas: HTMLCanvasElement,
  widget: WidgetLayout,
  bbox: SceneBbox,
  vehicle: ParkingSceneVehicle,
) {
  const center = worldToScreen(canvas, widget, bbox, vehicle.center[0], vehicle.center[2]);

  ctx.beginPath();
  ctx.arc(center.x, center.y, 7, 0, Math.PI * 2);
  ctx.fillStyle = "#f59e0b";
  ctx.fill();
  ctx.strokeStyle = "#fffbeb";
  ctx.lineWidth = 1.5;
  ctx.stroke();

  if (vehicle.direction) {
    const end = worldToScreen(
      canvas,
      widget,
      bbox,
      vehicle.center[0] + vehicle.direction[0] * 1.8,
      vehicle.center[2] + vehicle.direction[2] * 1.8,
    );
    drawArrow(ctx, center, end);
  }
}

function drawArrow(ctx: CanvasRenderingContext2D, from: ScreenPoint, to: ScreenPoint) {
  const angle = Math.atan2(to.y - from.y, to.x - from.x);
  const head = 6;

  ctx.beginPath();
  ctx.moveTo(from.x, from.y);
  ctx.lineTo(to.x, to.y);
  ctx.strokeStyle = "#fbbf24";
  ctx.lineWidth = 2;
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(to.x, to.y);
  ctx.lineTo(to.x - head * Math.cos(angle - Math.PI / 6), to.y - head * Math.sin(angle - Math.PI / 6));
  ctx.lineTo(to.x - head * Math.cos(angle + Math.PI / 6), to.y - head * Math.sin(angle + Math.PI / 6));
  ctx.closePath();
  ctx.fillStyle = "#fbbf24";
  ctx.fill();
}

function drawLegend(ctx: CanvasRenderingContext2D, canvas: HTMLCanvasElement, scene: ParkingScene | undefined) {
  const occupied = (scene?.containers ?? []).filter((container) => container.occupied).length;
  const free = Math.max((scene?.containers?.length ?? 0) - occupied, 0);
  const vehicles = scene?.vehicles?.length ?? 0;

  ctx.font = "12px Inter, Arial";
  ctx.textAlign = "left";
  ctx.textBaseline = "top";
  ctx.fillStyle = "rgba(2, 6, 23, 0.72)";
  ctx.fillRect(10, 10, 178, 28);
  ctx.fillStyle = "#e2e8f0";
  ctx.fillText(`Свободно: ${free}  Занято: ${occupied}  Авто: ${vehicles}`, 18, 17);
}

type SceneBbox = {
  minX: number;
  minZ: number;
  maxX: number;
  maxZ: number;
};

type ScreenPoint = {
  x: number;
  y: number;
};

function getSceneBbox(scene: ParkingScene | undefined): SceneBbox {
  if (scene?.bbox?.length === 4) {
    const [minX, minZ, maxX, maxZ] = scene.bbox;
    return { minX, minZ, maxX, maxZ };
  }

  return { minX: -10, minZ: -10, maxX: 10, maxZ: 10 };
}

function worldToScreen(
  canvas: HTMLCanvasElement,
  widget: WidgetLayout,
  bbox: SceneBbox,
  x: number,
  z: number,
): ScreenPoint {
  const centerX = (bbox.minX + bbox.maxX) / 2;
  const centerZ = (bbox.minZ + bbox.maxZ) / 2;
  const angle = (widget.rotation * Math.PI) / 180;
  const dx = x - centerX;
  const dz = z - centerZ;
  const rotatedX = dx * Math.cos(angle) - dz * Math.sin(angle);
  const rotatedZ = dx * Math.sin(angle) + dz * Math.cos(angle);

  return {
    x: canvas.width / 2 + widget.panX + rotatedX * widget.zoom,
    y: canvas.height / 2 + widget.panY + rotatedZ * widget.zoom,
  };
}

function average(points: ScreenPoint[]): ScreenPoint {
  const sum = points.reduce((acc, point) => ({ x: acc.x + point.x, y: acc.y + point.y }), { x: 0, y: 0 });
  return { x: sum.x / points.length, y: sum.y / points.length };
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
}

function normalizeRotation(value: unknown): WidgetLayout["rotation"] {
  if (value === 90 || value === 180 || value === 270) return value;
  return 0;
}
