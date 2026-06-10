import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Box,
  Camera,
  Check,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  RotateCw,
  Save,
  Trash2,
} from "lucide-react";
import {
  cameraApi,
  cvMarkupApi,
  cvMonitoringApi,
  parkingApi,
  type CameraRead,
  type MarkupContainerPayload,
  type ParkingRead,
  type ParkingSceneContainer,
  type Point2D,
  type Point3D,
} from "../../services/pmApi";

type MarkupContainer = {
  id: number;
  persistedId: number | null;
  spotId: number | null;
  name: string;
  imagePoints: Point2D[] | null;
  groundPoints: Point3D[] | null;
  upperPoints: Point3D[] | null;
  length: number;
  width: number;
  height: number;
  isBase: boolean;
};

type InfoTone = "normal" | "warning" | "error" | "success";

const DEFAULT_LENGTH = 5;
const DEFAULT_WIDTH = 2.5;
const DEFAULT_HEIGHT = 2;
const ROTATION_STEP = 0.03;

function toPoint2D(points: unknown): Point2D[] | null {
  if (!Array.isArray(points) || points.length !== 4) return null;
  const parsed = points.map((point) => {
    if (!Array.isArray(point) || point.length < 2) return null;
    const x = Number(point[0]);
    const y = Number(point[1]);
    return Number.isFinite(x) && Number.isFinite(y) ? ([x, y] as Point2D) : null;
  });
  return parsed.every(Boolean) ? (parsed as Point2D[]) : null;
}

function toPoint3D(points: unknown): Point3D[] | null {
  if (!Array.isArray(points) || points.length !== 4) return null;
  const parsed = points.map((point) => {
    if (!Array.isArray(point) || point.length < 3) return null;
    const x = Number(point[0]);
    const y = Number(point[1]);
    const z = Number(point[2]);
    return Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z) ? ([x, y, z] as Point3D) : null;
  });
  return parsed.every(Boolean) ? (parsed as Point3D[]) : null;
}

function containerFromScene(container: ParkingSceneContainer): MarkupContainer {
  return {
    id: container.id,
    persistedId: container.id,
    spotId: container.spot_id ?? null,
    name: container.name,
    imagePoints: toPoint2D(container.image_points),
    groundPoints: toPoint3D(container.ground_points),
    upperPoints: toPoint3D(container.upper_points),
    length: Number(container.length) || DEFAULT_LENGTH,
    width: Number(container.width) || DEFAULT_WIDTH,
    height: Number(container.height) || DEFAULT_HEIGHT,
    isBase: Boolean(container.is_base),
  };
}

function toPayload(container: MarkupContainer): MarkupContainerPayload {
  return {
    id: container.persistedId,
    spot_id: container.spotId,
    name: container.name,
    length: container.length,
    width: container.width,
    height: container.height,
    ground_points: container.groundPoints,
    upper_points: container.upperPoints,
    image_points: container.imagePoints,
    is_base: container.isBase,
  };
}

function pointInPolygon(px: number, pz: number, polygon: { x: number; z: number }[]) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i].x;
    const zi = polygon[i].z;
    const xj = polygon[j].x;
    const zj = polygon[j].z;
    const intersect = zi > pz !== zj > pz && px < ((xj - xi) * (pz - zi)) / (zj - zi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

function centroid2D(points: Point2D[]) {
  return {
    x: points.reduce((sum, point) => sum + point[0], 0) / points.length,
    y: points.reduce((sum, point) => sum + point[1], 0) / points.length,
  };
}

// Сравниваем imagePoints контейнера с тем, что пришло с сервера.
// Возвращает true если точки изменились и нужен пересчёт 3D.
function imagePointsChanged(
  container: MarkupContainer,
  serverMap: Map<number, Point2D[] | null>
): boolean {
  // Новый контейнер (без persistedId) — всегда нужен пересчёт
  if (container.persistedId == null) return true;

  const serverPoints = serverMap.get(container.persistedId);
  const current = container.imagePoints;

  if (serverPoints == null && current == null) return false;
  if (serverPoints == null || current == null) return true;
  if (serverPoints.length !== current.length) return true;

  return serverPoints.some(
    (p, i) => p[0] !== current[i][0] || p[1] !== current[i][1]
  );
}

export function ParkingMarker() {
  const imageCanvasRef = useRef<HTMLCanvasElement>(null);
  const topdownCanvasRef = useRef<HTMLCanvasElement>(null);
  const imageWrapRef = useRef<HTMLDivElement>(null);
  const topdownWrapRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const objectUrlRef = useRef<string | null>(null);
  const nextTempIdRef = useRef(-1);
  const dragPointRef = useRef<{ containerId: number; pointIndex: number } | null>(null);
  const panRef = useRef<{ active: boolean; x: number; y: number }>({ active: false, x: 0, y: 0 });

  // FIX 1: храним imageDisplay в ref чтобы canvasImagePoint всегда читал
  // актуальное значение даже если React state ещё не обновился (fullscreen-рассинхрон)
  const imageDisplayRef = useRef({ scale: 1, offsetX: 0, offsetY: 0 });

  // FIX 2: запоминаем imagePoints с сервера чтобы не пересчитывать 3D сцену
  // если точки не менялись
  const serverImagePointsRef = useRef<Map<number, Point2D[] | null>>(new Map());

  const [parkings, setParkings] = useState<ParkingRead[]>([]);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [parkingId, setParkingId] = useState<number | null>(null);
  const [cameras, setCameras] = useState<CameraRead[]>([]);
  const [currentCameraId, setCurrentCameraId] = useState<number | null>(null);
  const [containers, setContainers] = useState<MarkupContainer[]>([]);
  const [selectedContainerId, setSelectedContainerId] = useState<number | null>(null);
  const [drawingPoints, setDrawingPoints] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [currentDrawPoints, setCurrentDrawPoints] = useState<Point2D[]>([]);
  const [sceneBuilt, setSceneBuilt] = useState(false);
  const [unsavedChanges, setUnsavedChanges] = useState(false);
  const [imageSize, setImageSize] = useState({ width: 800, height: 600 });
  const [imageDisplay, setImageDisplay] = useState({ scale: 1, offsetX: 0, offsetY: 0 });
  const [topdownSize, setTopdownSize] = useState({ width: 600, height: 400 });
  const [view, setView] = useState({ centerX: 0, centerZ: 0, width: 20, angle: 0 });
  const imageContainerRef = useRef<HTMLDivElement>(null);

  const enterFullscreen = () => {
    imageContainerRef.current?.requestFullscreen();
  };

  const exitFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen();
  };

  const [info, setInfo] = useState<{ text: string; tone: InfoTone }>({
    text: "Камера не выбрана",
    tone: "normal",
  });
  const [newContainer, setNewContainer] = useState({
    name: "",
    length: DEFAULT_LENGTH,
    width: DEFAULT_WIDTH,
    height: DEFAULT_HEIGHT,
    isBase: false,
  });

  const selectedContainer = useMemo(
    () => containers.find((container) => container.id === selectedContainerId) ?? null,
    [containers, selectedContainerId]
  );

  const hasImage = imageRef.current != null;

  const setInfoText = useCallback((text: string, tone: InfoTone = "normal") => {
    setInfo({ text, tone });
  }, []);

  const resetInteraction = useCallback(() => {
    setSelectedContainerId(null);
    setDrawingPoints(false);
    setEditMode(false);
    setCurrentDrawPoints([]);
    dragPointRef.current = null;
  }, []);

  useEffect(() => {
    let cancelled = false;
    parkingApi
      .getAll({ page: 1, size: 200 })
      .then((response) => {
        if (cancelled) return;
        const items = response.data.items;
        setParkings(items);
        setParkingId((current) => current ?? items[0]?.id ?? null);
      })
      .catch(() => setInfoText("Ошибка загрузки парковок", "error"));
    return () => {
      cancelled = true;
    };
  }, [setInfoText]);

  useEffect(() => {
    if (parkingId == null) {
      setCameras([]);
      setCurrentCameraId(null);
      return;
    }
    let cancelled = false;
    cameraApi
      .getByParking(parkingId)
      .then((response) => {
        if (cancelled) return;
        const items = response.data.cameras;
        setCameras(items);
        setCurrentCameraId((current) => (current && items.some((camera) => camera.id === current) ? current : items[0]?.id ?? null));
      })
      .catch(() => setInfoText("Ошибка загрузки камер", "error"));
    return () => {
      cancelled = true;
    };
  }, [parkingId, setInfoText]);

  const recalcImageDisplay = useCallback(() => {
    const canvas = imageCanvasRef.current;
    const img = imageRef.current;
    if (!canvas) return;

    let width: number;
    let height: number;

    if (document.fullscreenElement) {
      width = window.screen.width;
      height = window.screen.height;
    } else {
      const wrap = imageWrapRef.current;
      if (!wrap) return;
      const rect = wrap.getBoundingClientRect();
      width = Math.max(320, Math.floor(rect.width));
      height = Math.max(360, Math.floor(rect.height));
    }

    canvas.width = width;
    canvas.height = height;
    setImageSize({ width, height });

    if (!img) {
      const display = { scale: 1, offsetX: 0, offsetY: 0 };
      imageDisplayRef.current = display; // FIX 1: синхронно обновляем ref
      setImageDisplay(display);
      return;
    }

    const scale = Math.min(width / img.naturalWidth, height / img.naturalHeight);
    const display = {
      scale,
      offsetX: (width - img.naturalWidth * scale) / 2,
      offsetY: (height - img.naturalHeight * scale) / 2,
    };
    imageDisplayRef.current = display; // FIX 1: синхронно обновляем ref
    setImageDisplay(display);
  }, []);

  useEffect(() => {
    const handler = () => {
      if (document.fullscreenElement) {
        setIsFullscreen(true);
      } else {
        setIsFullscreen(false);
      }
      // Пересчёт после того как браузер применил fullscreen и размеры известны
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          recalcImageDisplay();
        });
      });
    };
    document.addEventListener("fullscreenchange", handler);
    return () => document.removeEventListener("fullscreenchange", handler);
  }, [recalcImageDisplay]);

  const recalcTopdownSize = useCallback(() => {
    const canvas = topdownCanvasRef.current;
    const wrap = topdownWrapRef.current;
    if (!canvas || !wrap) return;
    const rect = wrap.getBoundingClientRect();
    const width = Math.max(320, Math.floor(rect.width));
    const height = Math.max(300, Math.floor(rect.height));
    canvas.width = width;
    canvas.height = height;
    setTopdownSize({ width, height });
  }, []);

  useEffect(() => {
    recalcImageDisplay();
    recalcTopdownSize();
    window.addEventListener("resize", recalcImageDisplay);
    window.addEventListener("resize", recalcTopdownSize);
    return () => {
      window.removeEventListener("resize", recalcImageDisplay);
      window.removeEventListener("resize", recalcTopdownSize);
    };
  }, [recalcImageDisplay, recalcTopdownSize]);

  const resetTopdownView = useCallback((items: MarkupContainer[]) => {
    const all = items.flatMap((container) => container.groundPoints ?? []);
    if (!all.length) {
      setView({ centerX: 0, centerZ: 0, width: 20, angle: 0 });
      return;
    }
    const xs = all.map((point) => point[0]);
    const zs = all.map((point) => point[2]);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minZ = Math.min(...zs);
    const maxZ = Math.max(...zs);
    const spanX = Math.max(maxX - minX, 1);
    const spanZ = Math.max(maxZ - minZ, 1);
    const aspect = topdownSize.width / topdownSize.height;
    setView({
      centerX: (minX + maxX) / 2,
      centerZ: (minZ + maxZ) / 2,
      width: Math.max(spanX * 1.25, spanZ * aspect * 1.25, 5),
      angle: 0,
    });
  }, [topdownSize.height, topdownSize.width]);

  const loadCamera = useCallback(async () => {
    if (currentCameraId == null) return;
    resetInteraction();
    setContainers([]);
    setUnsavedChanges(false);
    setSceneBuilt(false);
    setInfoText("Загрузка камеры...", "normal");

    try {
      const [frameResponse, scenesResponse] = await Promise.all([
        fetch(cvMarkupApi.getFrameUrl(currentCameraId)),
        cvMonitoringApi.getScenes(),
      ]);

      if (!frameResponse.ok) {
        let detail = "Не удалось загрузить кадр камеры";
        try {
          const payload = await frameResponse.json();
          if (payload?.detail) detail = String(payload.detail);
        } catch {
          detail = await frameResponse.text();
        }
        throw new Error(detail || "Не удалось загрузить кадр камеры");
      }

      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = URL.createObjectURL(await frameResponse.blob());
      const img = new Image();
      await new Promise<void>((resolve, reject) => {
        img.onload = () => resolve();
        img.onerror = () => reject(new Error("Не удалось прочитать изображение камеры"));
        img.src = objectUrlRef.current as string;
      });
      imageRef.current = img;
      recalcImageDisplay();

      const scene = scenesResponse.data.data[String(currentCameraId)];
      const loadedContainers = (scene?.containers ?? []).map(containerFromScene);
      setContainers(loadedContainers);

      // FIX 2: запоминаем imagePoints с сервера как эталон
      serverImagePointsRef.current = new Map(
        loadedContainers.map((c) => [c.persistedId ?? c.id, c.imagePoints])
      );

      const hasGround = loadedContainers.some((container) => container.groundPoints?.length === 4);
      setSceneBuilt(hasGround);
      resetTopdownView(loadedContainers);
      setInfoText(`Камера ${currentCameraId}, загружено ${loadedContainers.length} мест`, "success");
    } catch (error) {
      imageRef.current = null;
      recalcImageDisplay();
      const message = error instanceof Error ? error.message : "Ошибка загрузки камеры";
      setInfoText(message, "error");
    }
  }, [currentCameraId, recalcImageDisplay, resetInteraction, resetTopdownView, setInfoText]);

  const worldToScreen = useCallback(
    (x: number, z: number) => {
      const viewHeight = view.width * (topdownSize.height / topdownSize.width);
      const dx = x - view.centerX;
      const dz = z - view.centerZ;
      const cos = Math.cos(-view.angle);
      const sin = Math.sin(-view.angle);
      const rotatedX = dx * cos - dz * sin;
      const rotatedZ = dx * sin + dz * cos;
      return {
        x: (rotatedX / view.width) * topdownSize.width + topdownSize.width / 2,
        y: (rotatedZ / viewHeight) * topdownSize.height + topdownSize.height / 2,
      };
    },
    [topdownSize.height, topdownSize.width, view]
  );

  const screenToWorld = useCallback(
    (x: number, y: number) => {
      const viewHeight = view.width * (topdownSize.height / topdownSize.width);
      const rotatedX = ((x - topdownSize.width / 2) / topdownSize.width) * view.width;
      const rotatedZ = ((y - topdownSize.height / 2) / topdownSize.height) * viewHeight;
      const cos = Math.cos(view.angle);
      const sin = Math.sin(view.angle);
      return {
        x: view.centerX + rotatedX * cos - rotatedZ * sin,
        z: view.centerZ + rotatedX * sin + rotatedZ * cos,
      };
    },
    [topdownSize.height, topdownSize.width, view]
  );

  const worldDeltaFromScreenDelta = useCallback(
    (dx: number, dy: number) => {
      const before = screenToWorld(topdownSize.width / 2, topdownSize.height / 2);
      const after = screenToWorld(topdownSize.width / 2 + dx, topdownSize.height / 2 + dy);
      return { dx: after.x - before.x, dz: after.z - before.z };
    },
    [screenToWorld, topdownSize.height, topdownSize.width]
  );

  const drawImage = useCallback(() => {
    const canvas = imageCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    const img = imageRef.current;
    if (img) {
      ctx.drawImage(
        img,
        0,
        0,
        img.naturalWidth,
        img.naturalHeight,
        imageDisplay.offsetX,
        imageDisplay.offsetY,
        img.naturalWidth * imageDisplay.scale,
        img.naturalHeight * imageDisplay.scale
      );
    } else {
      ctx.fillStyle = "#9CA3AF";
      ctx.font = "16px Arial";
      ctx.textAlign = "center";
      ctx.fillText("Загрузите камеру", canvas.width / 2, canvas.height / 2);
    }

    const drawContainer = (container: MarkupContainer, highlight = false) => {
      if (!container.imagePoints?.length) return;
      const pts = container.imagePoints.map((point) => ({
        x: imageDisplay.offsetX + point[0] * imageDisplay.scale,
        y: imageDisplay.offsetY + point[1] * imageDisplay.scale,
      }));
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(pts[0].x, pts[0].y);
      pts.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
      ctx.closePath();
      ctx.strokeStyle = highlight ? "#2563EB" : container.isBase ? "#16A34A" : "#F59E0B";
      ctx.lineWidth = highlight ? 3 : 2;
      ctx.stroke();
      ctx.fillStyle = highlight ? "rgba(37,99,235,0.18)" : container.isBase ? "rgba(22,163,74,0.16)" : "rgba(245,158,11,0.16)";
      ctx.fill();
      const center = centroid2D(pts.map((point) => [point.x, point.y]));
      ctx.fillStyle = "white";
      ctx.font = "12px Arial";
      ctx.textAlign = "center";
      ctx.fillText(container.name, center.x, center.y - 4);
      if (container.isBase) {
        ctx.fillStyle = "gold";
        ctx.fillText("BASE", center.x, center.y + 12);
      }
      ctx.restore();
    };

    containers.forEach((container) => drawContainer(container, container.id === selectedContainerId && editMode));

    if (drawingPoints && currentDrawPoints.length) {
      ctx.save();
      ctx.strokeStyle = "#FFAA00";
      ctx.fillStyle = "#FFAA00";
      const pts = currentDrawPoints.map((point) => ({
        x: imageDisplay.offsetX + point[0] * imageDisplay.scale,
        y: imageDisplay.offsetY + point[1] * imageDisplay.scale,
      }));
      pts.forEach((point, index) => {
        ctx.beginPath();
        ctx.arc(point.x, point.y, 6, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "white";
        ctx.font = "bold 14px Arial";
        ctx.fillText(String(index + 1), point.x + 8, point.y - 4);
        ctx.fillStyle = "#FFAA00";
      });
      if (pts.length >= 2) {
        ctx.beginPath();
        ctx.moveTo(pts[0].x, pts[0].y);
        pts.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
        if (pts.length === 4) ctx.closePath();
        ctx.stroke();
      }
      ctx.restore();
    }

    if (editMode && selectedContainer?.imagePoints) {
      ctx.save();
      selectedContainer.imagePoints.forEach((point, index) => {
        const x = imageDisplay.offsetX + point[0] * imageDisplay.scale;
        const y = imageDisplay.offsetY + point[1] * imageDisplay.scale;
        ctx.beginPath();
        ctx.arc(x, y, 8, 0, Math.PI * 2);
        ctx.fillStyle = "#2563EB";
        ctx.fill();
        ctx.fillStyle = "black";
        ctx.font = "bold 12px Arial";
        ctx.fillText(String(index + 1), x + 4, y - 4);
      });
      ctx.restore();
    }
  }, [containers, currentDrawPoints, drawingPoints, editMode, imageDisplay, selectedContainer, selectedContainerId]);

  const drawTopdown = useCallback(() => {
    const canvas = topdownCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#F3F4F6";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    containers.forEach((container) => {
      if (!container.groundPoints?.length) return;
      const pts = container.groundPoints.map((point) => worldToScreen(point[0], point[2]));
      const highlight = container.id === selectedContainerId;
      ctx.beginPath();
      ctx.moveTo(pts[0].x, pts[0].y);
      pts.slice(1).forEach((point) => ctx.lineTo(point.x, point.y));
      ctx.closePath();
      ctx.fillStyle = highlight ? "rgba(37,99,235,0.20)" : "rgba(37,99,235,0.12)";
      ctx.fill();
      ctx.strokeStyle = highlight ? "#2563EB" : "#3B82F6";
      ctx.lineWidth = highlight ? 2 : 1;
      ctx.stroke();
      const centerX = pts.reduce((sum, point) => sum + point.x, 0) / pts.length;
      const centerY = pts.reduce((sum, point) => sum + point.y, 0) / pts.length;
      ctx.fillStyle = "#111827";
      ctx.font = "12px Arial";
      ctx.textAlign = "center";
      ctx.fillText(container.name, centerX, centerY - 4);
      if (container.isBase) {
        ctx.fillStyle = "gold";
        ctx.fillText("BASE", centerX, centerY + 12);
      }
    });
  }, [containers, selectedContainerId, worldToScreen]);

  useEffect(() => {
    drawImage();
  }, [drawImage, imageSize]);

  useEffect(() => {
    drawTopdown();
  }, [drawTopdown, topdownSize]);

  // FIX 1: читаем из ref а не из state — всегда актуальное значение масштаба,
  // даже если React ещё не успел обновить state после перехода в fullscreen
  const canvasImagePoint = (event: React.MouseEvent<HTMLCanvasElement>): Point2D | null => {
    const img = imageRef.current;
    const canvas = imageCanvasRef.current;
    if (!img || !canvas) return null;
    const display = imageDisplayRef.current;
    const rect = canvas.getBoundingClientRect();
    const x = (event.clientX - rect.left - display.offsetX) / display.scale;
    const y = (event.clientY - rect.top - display.offsetY) / display.scale;
    if (x < 0 || y < 0 || x > img.naturalWidth || y > img.naturalHeight) return null;
    return [x, y];
  };

  const addNewContainer = () => {
    if (!hasImage) {
      window.alert("Сначала загрузите камеру");
      return;
    }
    const name = newContainer.name.trim() || `Spot_${containers.length + 1}`;
    const id = nextTempIdRef.current--;
    const item: MarkupContainer = {
      id,
      persistedId: null,
      spotId: null,
      name,
      imagePoints: null,
      groundPoints: null,
      upperPoints: null,
      length: newContainer.length,
      width: newContainer.width,
      height: newContainer.height,
      isBase: newContainer.isBase,
    };
    setContainers((current) => [...current, item]);
    setSelectedContainerId(id);
    setDrawingPoints(false);
    setEditMode(false);
    setCurrentDrawPoints([]);
    setSceneBuilt(false);
    setUnsavedChanges(true);
    setInfoText(`Добавлен контейнер "${name}". Теперь нарисуйте 4 точки.`, "warning");
  };

  const startDrawing = () => {
    if (selectedContainerId == null) {
      window.alert("Сначала выберите контейнер");
      return;
    }
    setDrawingPoints(true);
    setEditMode(false);
    setCurrentDrawPoints([]);
    enterFullscreen();
    setInfoText(`Рисуйте 4 точки углов контейнера "${selectedContainer?.name ?? ""}" по часовой стрелке.`, "warning");
  };

  const finishDrawing = () => {
    if (selectedContainerId == null || currentDrawPoints.length !== 4) {
      window.alert("Нужно ровно 4 точки");
      return;
    }
    setContainers((current) =>
      current.map((container) =>
        container.id === selectedContainerId
          ? { ...container, imagePoints: currentDrawPoints, groundPoints: null, upperPoints: null }
          : container
      )
    );
    setDrawingPoints(false);
    setCurrentDrawPoints([]);
    setSceneBuilt(false);
    setUnsavedChanges(true);
    exitFullscreen();
    setInfoText("Точки сохранены. Теперь нажмите «Построить 3D сцену».", "warning");
  };

  const deleteSelectedContainer = () => {
    if (selectedContainerId == null) return;
    const container = selectedContainer;
    if (!container) return;
    if (!window.confirm(`Удалить контейнер "${container.name}"?`)) return;
    setContainers((current) => current.filter((item) => item.id !== selectedContainerId));
    resetInteraction();
    setSceneBuilt(false);
    setUnsavedChanges(true);
    setInfoText("Контейнер удалён", "warning");
  };

  const build3DScene = async () => {
  if (currentCameraId == null || !imageRef.current) {
    window.alert("Сначала загрузите камеру");
    return;
  }
  if (!containers.length) {
    window.alert("Нет ни одного контейнера");
    return;
  }
  if (containers.filter((c) => c.isBase).length !== 1) {
    window.alert("Для построения 3D сцены нужен ровно один базовый контейнер");
    return;
  }
  const withoutPoints = containers.find(
    (c) => !c.imagePoints || c.imagePoints.length !== 4
  );
  if (withoutPoints) {
    window.alert(`Контейнер "${withoutPoints.name}" не имеет 4 точек на изображении`);
    return;
  }

  const base = containers.find((c) => c.isBase)!;

  // Контейнеры которым нужен пересчёт
  const needRebuildSet = new Set(
    containers
      .filter(
        (c) =>
          imagePointsChanged(c, serverImagePointsRef.current) ||
          !c.groundPoints ||
          !c.upperPoints
      )
      .map((c) => c.id)
  );

  if (needRebuildSet.size === 0) {
    setSceneBuilt(true);
    setInfoText("3D сцена актуальна, пересчёт не требуется.", "success");
    return;
  }

  // На сервер: все нуждающиеся + базовый (нужен для гомографии)
  const payloadContainers = containers.filter(
    (c) => needRebuildSet.has(c.id) || c.isBase
  );

  try {
    setInfoText("Построение 3D сцены...", "normal");
    const response = await cvMarkupApi.buildScene({
      camera_id: currentCameraId,
      image_width: imageRef.current.naturalWidth,
      image_height: imageRef.current.naturalHeight,
      containers: payloadContainers.map(toPayload),
    });

    // Сервер вернул результаты в том же порядке что payloadContainers.
    // Строим маппинг по имени (имя — единственный стабильный ключ для новых контейнеров).
    // persistedId надёжнее для существующих.
    const rebuiltByPersistedId = new Map<number, MarkupContainer>();
    const rebuiltByName = new Map<string, MarkupContainer>();

    response.data.containers.forEach((serverContainer, index) => {
      const item = containerFromScene(serverContainer);
      const original = payloadContainers[index]; // порядок сохраняется

      // Восстанавливаем фронтовые id
      const merged: MarkupContainer = {
        ...item,
        id: original.id,                          // сохраняем фронтовый id (может быть отрицательным)
        persistedId: item.persistedId,            // новый persistedId от сервера
        spotId: original.spotId ?? item.spotId,
      };

      if (merged.persistedId != null) {
        rebuiltByPersistedId.set(merged.persistedId, merged);
      }
      rebuiltByName.set(original.name, merged);   // ключ — имя из оригинала
    });

    // Мержим: каждый контейнер получает свежие данные если был в запросе,
    // иначе остаётся нетронутым
    const mergedContainers = containers.map((c) => {
      if (!needRebuildSet.has(c.id) && !c.isBase) return c; // не участвовал — не трогаем

      // Для base: если он не нуждался в пересчёте — тоже оставляем как есть
      if (c.isBase && !needRebuildSet.has(c.id)) return c;

      const fresh =
        (c.persistedId != null ? rebuiltByPersistedId.get(c.persistedId) : null) ??
        rebuiltByName.get(c.name);

      return fresh ?? c;
    });

    setContainers(mergedContainers);
    setSceneBuilt(true);
    setUnsavedChanges(true);
    resetTopdownView(mergedContainers);
    setInfoText("3D сцена построена. Проверьте вид сверху и нажмите «Подтвердить».", "success");
  } catch (error) {
    const message = error instanceof Error ? error.message : "Ошибка построения 3D сцены";
    setInfoText(message, "error");
    window.alert(message);
  }
};

  const confirmAndSave = async () => {
    if (currentCameraId == null) return;
    if (!sceneBuilt) {
      window.alert("Сначала постройте 3D сцену");
      return;
    }
    const invalid = containers.find((container) => !container.groundPoints || !container.upperPoints);
    if (invalid) {
      window.alert(`Контейнер "${invalid.name}" не имеет 3D координат`);
      return;
    }
    try {
      setInfoText("Сохранение разметки...", "normal");
      const response = await cvMarkupApi.save({
        camera_id: currentCameraId,
        replace_existing: true,
        containers: containers.map(toPayload),
      });
      const saved = response.data.saved.map(containerFromScene);
      setContainers(saved);
      setSceneBuilt(true);
      setUnsavedChanges(false);

      // FIX 2: обновляем эталон после успешного сохранения
      serverImagePointsRef.current = new Map(
        saved.map((c) => [c.persistedId ?? c.id, c.imagePoints])
      );

      resetTopdownView(saved);
      setInfoText("Сцена сохранена", "success");
    } catch (error) {
      const message = error instanceof Error ? error.message : "Ошибка сохранения сцены";
      setInfoText(message, "error");
      window.alert(message);
    }
  };

  const moveSelectedByScreenDir = (dirX: number, dirY: number) => {
    if (selectedContainerId == null) {
      window.alert("Выберите контейнер на виде сверху");
      return;
    }
    const delta = worldDeltaFromScreenDelta(dirX * topdownSize.width * 0.02, dirY * topdownSize.width * 0.02);
    setContainers((current) =>
      current.map((container) => {
        if (container.id !== selectedContainerId || !container.groundPoints || container.isBase) return container;
        const groundPoints = container.groundPoints.map((point) => [point[0] + delta.dx, point[1], point[2] + delta.dz] as Point3D);
        const upperPoints = container.upperPoints?.map((point) => [point[0] + delta.dx, point[1], point[2] + delta.dz] as Point3D) ?? null;
        return { ...container, groundPoints, upperPoints };
      })
    );
    setUnsavedChanges(true);
  };

  const rotateSelected = (angle: number) => {
    if (selectedContainerId == null) {
      window.alert("Выберите контейнер");
      return;
    }
    setContainers((current) =>
      current.map((container) => {
        if (container.id !== selectedContainerId || !container.groundPoints || container.isBase) return container;
        const cx = container.groundPoints.reduce((sum, point) => sum + point[0], 0) / 4;
        const cz = container.groundPoints.reduce((sum, point) => sum + point[2], 0) / 4;
        const rotate = (point: Point3D): Point3D => {
          const dx = point[0] - cx;
          const dz = point[2] - cz;
          return [cx + dx * Math.cos(angle) - dz * Math.sin(angle), point[1], cz + dx * Math.sin(angle) + dz * Math.cos(angle)];
        };
        return {
          ...container,
          groundPoints: container.groundPoints.map(rotate),
          upperPoints: container.upperPoints?.map(rotate) ?? null,
        };
      })
    );
    setUnsavedChanges(true);
  };

  const onImageClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!drawingPoints) return;
    const point = canvasImagePoint(event);
    if (!point || currentDrawPoints.length >= 4) return;
    setCurrentDrawPoints((current) => [...current, point]);
  };

  const onImageMouseDown = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!editMode || selectedContainerId == null || !selectedContainer?.imagePoints) return;
    const point = canvasImagePoint(event);
    if (!point) return;
    // FIX 1: используем ref для hit-теста — актуальный scale без задержки
    const display = imageDisplayRef.current;
    const hitIndex = selectedContainer.imagePoints.findIndex((candidate) => Math.hypot(candidate[0] - point[0], candidate[1] - point[1]) < 12 / display.scale);
    if (hitIndex !== -1) dragPointRef.current = { containerId: selectedContainerId, pointIndex: hitIndex };
  };

  const onImageMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const drag = dragPointRef.current;
    if (!drag) return;
    const point = canvasImagePoint(event);
    if (!point) return;
    setContainers((current) =>
      current.map((container) => {
        if (container.id !== drag.containerId || !container.imagePoints) return container;
        const imagePoints = [...container.imagePoints];
        imagePoints[drag.pointIndex] = point;
        return { ...container, imagePoints, groundPoints: null, upperPoints: null };
      })
    );
    setSceneBuilt(false);
    setUnsavedChanges(true);
  };

  const onTopdownClick = (event: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = topdownCanvasRef.current;
    if (!canvas || panRef.current.active) return;
    const rect = canvas.getBoundingClientRect();
    const world = screenToWorld(event.clientX - rect.left, event.clientY - rect.top);
    const hit = containers.find((container) => {
      if (!container.groundPoints) return false;
      return pointInPolygon(
        world.x,
        world.z,
        container.groundPoints.map((point) => ({ x: point[0], z: point[2] }))
      );
    });
    setSelectedContainerId(hit?.id ?? null);
    setEditMode(false);
  };

  const onTopdownWheel = (event: React.WheelEvent<HTMLCanvasElement>) => {
    event.preventDefault();
    const canvas = topdownCanvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mouseX = event.clientX - rect.left;
    const mouseY = event.clientY - rect.top;
    const before = screenToWorld(mouseX, mouseY);
    const nextWidth = Math.min(200, Math.max(0.5, view.width * (event.deltaY > 0 ? 1.1 : 0.9)));
    const oldView = view;
    const viewHeight = nextWidth * (topdownSize.height / topdownSize.width);
    const rotatedX = ((mouseX - topdownSize.width / 2) / topdownSize.width) * nextWidth;
    const rotatedZ = ((mouseY - topdownSize.height / 2) / topdownSize.height) * viewHeight;
    const cos = Math.cos(oldView.angle);
    const sin = Math.sin(oldView.angle);
    const afterOffsetX = rotatedX * cos - rotatedZ * sin;
    const afterOffsetZ = rotatedX * sin + rotatedZ * cos;
    setView({ ...oldView, width: nextWidth, centerX: before.x - afterOffsetX, centerZ: before.z - afterOffsetZ });
  };

  const onTopdownMouseMove = (event: React.MouseEvent<HTMLCanvasElement>) => {
    if (!panRef.current.active) return;
    const dx = event.clientX - panRef.current.x;
    const dy = event.clientY - panRef.current.y;
    const delta = worldDeltaFromScreenDelta(dx, dy);
    panRef.current = { active: true, x: event.clientX, y: event.clientY };
    setView((current) => ({ ...current, centerX: current.centerX - delta.dx, centerZ: current.centerZ - delta.dz }));
  };

  const infoColor = {
    normal: "#374151",
    warning: "#D97706",
    error: "#DC2626",
    success: "#16A34A",
  }[info.tone];

  const buttonClass = "m-1 inline-flex items-center gap-2 px-3 py-1.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed";
  const secondaryButtonClass = "m-1 inline-flex items-center gap-2 px-3 py-1.5 bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed";
  const iconButtonClass = "m-1 inline-flex h-9 w-9 items-center justify-center bg-white text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed";
  const fieldClass = "w-full bg-white text-gray-900 border border-gray-300 rounded-lg p-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500";
  const inputClass = "m-1 px-3 py-1.5 text-gray-900 bg-white border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500";

  return (
    <div className="min-h-full bg-gray-50 p-6 text-gray-900 font-[Arial,sans-serif] overflow-auto">
      <div className="flex gap-5 min-w-[980px]">
        <aside className="w-80 max-h-[90vh] overflow-y-auto rounded-lg bg-white border border-gray-200 shadow-sm p-4 shrink-0">
          <h2 className="text-2xl font-semibold mb-4">Разметка парковки</h2>

          <section className="space-y-2">
            <h3 className="text-lg font-semibold">Камеры</h3>
            <select
              value={parkingId ?? ""}
              onChange={(event) => setParkingId(Number(event.target.value))}
              className={fieldClass}
            >
              {parkings.map((parking) => (
                <option key={parking.id} value={parking.id}>
                  {parking.name}
                </option>
              ))}
            </select>
            <select
              size={4}
              value={currentCameraId ?? ""}
              onChange={(event) => setCurrentCameraId(Number(event.target.value))}
              className={fieldClass}
            >
              {cameras.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.id}: {camera.rtsp_url}
                </option>
              ))}
            </select>
            <button className={buttonClass} onClick={loadCamera}>
              <Camera className="h-4 w-4" />
              Загрузить камеру
            </button>
          </section>

          <hr className="border-gray-200 my-3" />

          <section className="space-y-2">
            <h3 className="text-lg font-semibold">Контейнеры</h3>
            <select
              size={6}
              value={selectedContainerId ?? ""}
              onChange={(event) => {
                setSelectedContainerId(Number(event.target.value));
                setEditMode(false);
              }}
              className={fieldClass}
            >
              {containers.map((container) => (
                <option key={container.id} value={container.id}>
                  {container.name} ({container.length}x{container.width}x{container.height}){" "}
                  {container.isBase ? "Базовый" : container.groundPoints ? "3D" : "нет 3D"}
                </option>
              ))}
            </select>
            <div className="text-sm">
              <span>Выбран: {selectedContainer?.name ?? "—"}</span>
              <span className="ml-3">Статус: {selectedContainer?.groundPoints ? "3D готов" : selectedContainer ? "только 2D" : "—"}</span>
            </div>
            <div>
              <button className={buttonClass} onClick={addNewContainer}>
                <Plus className="h-4 w-4" />
                Добавить
              </button>
              <button
                className={secondaryButtonClass}
                disabled={selectedContainerId == null}
                onClick={() => {
                  if (!selectedContainer?.imagePoints) {
                    window.alert("Сначала нарисуйте 4 точки для этого контейнера");
                    return;
                  }
                  setEditMode(true);
                  setDrawingPoints(false);
                  setInfoText("Режим редактирования точек. Перетаскивайте точки мышью.", "warning");
                }}
              >
                <Pencil className="h-4 w-4" />
                Редактировать точки
              </button>
              <button
                className={secondaryButtonClass}
                disabled={selectedContainerId == null}
                onClick={deleteSelectedContainer}
              >
                <Trash2 className="h-4 w-4" />
                Удалить
              </button>
              <button
                className={buttonClass}
                disabled={!containers.some((container) => container.imagePoints?.length === 4) || drawingPoints}
                onClick={build3DScene}
              >
                <Box className="h-4 w-4" />
                Построить 3D сцену
              </button>
            </div>
          </section>

          <hr className="border-gray-200 my-3" />

          <section className="space-y-2">
            <h3 className="text-lg font-semibold">Параметры нового места</h3>
            <label className="block">
              Имя:
              <input
                className={`${inputClass} w-[190px]`}
                value={newContainer.name}
                onChange={(event) => setNewContainer((current) => ({ ...current, name: event.target.value }))}
                placeholder="Название"
              />
            </label>
            <label>
              Длина:
              <input
                className={`${inputClass} w-24`}
                type="number"
                step="0.1"
                value={newContainer.length}
                onChange={(event) => setNewContainer((current) => ({ ...current, length: Number(event.target.value) }))}
              />
            </label>
            <label>
              Ширина:
              <input
                className={`${inputClass} w-24`}
                type="number"
                step="0.1"
                value={newContainer.width}
                onChange={(event) => setNewContainer((current) => ({ ...current, width: Number(event.target.value) }))}
              />
            </label>
            <label>
              Высота:
              <input
                className={`${inputClass} w-24`}
                type="number"
                step="0.1"
                value={newContainer.height}
                onChange={(event) => setNewContainer((current) => ({ ...current, height: Number(event.target.value) }))}
              />
            </label>
            <label className="block">
              <input
                className="m-1"
                type="checkbox"
                checked={newContainer.isBase}
                onChange={(event) => setNewContainer((current) => ({ ...current, isBase: event.target.checked }))}
              />
              Базовое
            </label>
            <button
              className={secondaryButtonClass}
              disabled={selectedContainerId == null || drawingPoints}
              onClick={startDrawing}
            >
              <Plus className="h-4 w-4" />
              Рисовать точки
            </button>
            <button
              className={buttonClass}
              disabled={selectedContainerId == null || !drawingPoints || currentDrawPoints.length !== 4}
              onClick={finishDrawing}
            >
              <Check className="h-4 w-4" />
              Закончить 4 точки
            </button>
          </section>

          <hr className="border-gray-200 my-3" />

          <section>
            <button className={buttonClass} disabled={!unsavedChanges} onClick={confirmAndSave}>
              <Save className="h-4 w-4" />
              Сохранить все изменения
            </button>
            <button className={secondaryButtonClass} onClick={loadCamera}>
              <RefreshCw className="h-4 w-4" />
              Перезагрузить камеру
            </button>
          </section>
          <div className="mt-2 text-sm" style={{ color: infoColor }}>
            {info.text}
          </div>
        </aside>

        <main className="flex-1 min-w-0">
          <section className="rounded-lg bg-white border border-gray-200 shadow-sm p-4 mb-5">
            <h3 className="text-lg font-semibold mb-3">Изображение с камеры</h3>
            <div
              ref={imageContainerRef}
              className={isFullscreen ? "bg-black" : ""}
              style={isFullscreen ? { width: "100vw", height: "100vh", display: "flex", flexDirection: "column" } : undefined}
            >
              {isFullscreen && (
                <div className="flex items-center justify-between px-4 py-2 shrink-0">
                  <span className="text-yellow-400 text-sm font-medium">
                    {info.text} — точек: {currentDrawPoints.length}/4
                  </span>
                  <div className="flex gap-3">
                    <button
                      className="px-3 py-1.5 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
                      disabled={currentDrawPoints.length !== 4}
                      onClick={finishDrawing}
                    >
                      ✓ Готово
                    </button>
                    <button
                      className="px-3 py-1.5 bg-red-600 text-white rounded-lg hover:bg-red-700"
                      onClick={() => {
                        exitFullscreen();
                        setDrawingPoints(false);
                        setCurrentDrawPoints([]);
                        setInfoText("Рисование отменено", "warning");
                      }}
                    >
                      ✕ Отмена (Esc)
                    </button>
                  </div>
                </div>
              )}
              <div
                ref={imageWrapRef}
                style={isFullscreen ? { flex: 1, minHeight: 0 } : undefined}
                className={isFullscreen ? "" : "h-[58vh] min-h-[430px]"}
              >
                <canvas
                  ref={imageCanvasRef}
                  onClick={onImageClick}
                  onMouseDown={onImageMouseDown}
                  onMouseMove={onImageMouseMove}
                  onMouseUp={() => { dragPointRef.current = null; }}
                  className={`w-full h-full bg-black border border-gray-300 rounded-md ${
                    drawingPoints ? "cursor-crosshair" : editMode ? "cursor-move" : "cursor-default"
                  }`}
                />
              </div>
            </div>
          </section>

          <section className="rounded-lg bg-white border border-gray-200 shadow-sm p-4">
            <h3 className="text-lg font-semibold mb-3">Вид сверху (редактирование)</h3>
            <div ref={topdownWrapRef} className="h-[36vh] min-h-[320px]">
              <canvas
                ref={topdownCanvasRef}
                onClick={onTopdownClick}
                onWheel={onTopdownWheel}
                onMouseDown={(event) => {
                  panRef.current = { active: true, x: event.clientX, y: event.clientY };
                }}
                onMouseMove={onTopdownMouseMove}
                onMouseUp={() => {
                  panRef.current.active = false;
                }}
                onMouseLeave={() => {
                  panRef.current.active = false;
                }}
                className="w-full h-full bg-gray-100 border border-gray-300 rounded-md cursor-grab active:cursor-grabbing"
              />
            </div>
            <div className="mt-2 text-sm">
              <span>Выбрано: {selectedContainer?.name ?? "—"}</span>
              <button className={iconButtonClass} title="Вверх" onClick={() => moveSelectedByScreenDir(0, -1)}>
                <ArrowUp className="h-4 w-4" />
              </button>
              <button className={iconButtonClass} title="Вниз" onClick={() => moveSelectedByScreenDir(0, 1)}>
                <ArrowDown className="h-4 w-4" />
              </button>
              <button className={iconButtonClass} title="Влево" onClick={() => moveSelectedByScreenDir(-1, 0)}>
                <ArrowLeft className="h-4 w-4" />
              </button>
              <button className={iconButtonClass} title="Вправо" onClick={() => moveSelectedByScreenDir(1, 0)}>
                <ArrowRight className="h-4 w-4" />
              </button>
              <button className={secondaryButtonClass} title="Повернуть против часовой" onClick={() => rotateSelected(-ROTATION_STEP)}>
                <RotateCcw className="h-4 w-4" />
                Против часовой
              </button>
              <button className={secondaryButtonClass} title="Повернуть по часовой" onClick={() => rotateSelected(ROTATION_STEP)}>
                <RotateCw className="h-4 w-4" />
                По часовой
              </button>
              <button className={secondaryButtonClass} onClick={() => setView((current) => ({ ...current, angle: (current.angle + Math.PI / 2) % (Math.PI * 2) }))}>
                <RotateCw className="h-4 w-4" />
                Повернуть вид
              </button>
              <button className={buttonClass} disabled={!sceneBuilt || !unsavedChanges} onClick={confirmAndSave}>
                <Check className="h-4 w-4" />
                Подтвердить и сохранить
              </button>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
}