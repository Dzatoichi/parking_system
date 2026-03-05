import React, { useEffect, useMemo, useRef, useState } from "react";
import { Check, ParkingSquare, Plus, Trash2 } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { parkingApi, spotApi, type ParkingRead, type SpotCoordinates, type SpotRead, type SpotReadShort, type SpotType } from "../../services/pmApi";

type Mode = "idle" | "create" | "edit";

function centerOf(points: number[][]) {
  const xs = points.map((p) => p[0]);
  const ys = points.map((p) => p[1]);
  const cx = xs.reduce((a, b) => a + b, 0) / xs.length;
  const cy = ys.reduce((a, b) => a + b, 0) / ys.length;
  return { cx, cy };
}

export function ParkingMarker() {
  const qc = useQueryClient();
  const [parkingId, setParkingId] = useState<number | null>(null);
  const [mode, setMode] = useState<Mode>("idle");
  const [spotNumber, setSpotNumber] = useState("");
  const [spotType, setSpotType] = useState<SpotType>("STANDARD");
  const [activeSpotId, setActiveSpotId] = useState<number | null>(null);
  const [bgImage, setBgImage] = useState<string | null>(null);
  const [points, setPoints] = useState<number[][]>([]);

  const { data: parkingsResp } = useQuery({
    queryKey: ["parkings"],
    queryFn: () => parkingApi.getAll({ page: 1, size: 200 }),
    retry: false,
  });
  const parkings = parkingsResp?.data?.items ?? [];

  const effectiveParkingId = useMemo(() => {
    if (parkingId != null) return parkingId;
    return parkings[0]?.id ?? null;
  }, [parkingId, parkings]);

  const { data: spotsResp } = useQuery({
    queryKey: ["spotsByParking", effectiveParkingId],
    queryFn: () => spotApi.getByParking(effectiveParkingId as number, { page: 1, size: 200 }),
    enabled: effectiveParkingId != null,
    retry: false,
  });
  const spots = spotsResp?.data?.items ?? [];

  const { data: activeSpotDetailResp } = useQuery({
    queryKey: ["spotDetail", activeSpotId],
    queryFn: () => spotApi.getDetail(activeSpotId as number),
    enabled: activeSpotId != null && mode === "edit",
    retry: false,
  });

  useEffect(() => {
    if (mode === "edit" && activeSpotDetailResp?.data) {
      const s = activeSpotDetailResp.data as SpotRead;
      setSpotNumber(s.spot_number);
      setSpotType(s.spot_type);
      setPoints(s.spot_coordinates.points);
    }
  }, [activeSpotDetailResp, mode]);

  const createMutation = useMutation({
    mutationFn: async () => {
      const { cx, cy } = centerOf(points);
      const coords: SpotCoordinates = { points, center_x: cx, center_y: cy };
      return spotApi.create(effectiveParkingId as number, {
        spot_number: spotNumber,
        spot_type: spotType,
        spot_coordinates: coords,
      });
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["spotsByParking", effectiveParkingId] });
      resetEditor();
    },
  });

  const updateMutation = useMutation({
    mutationFn: async () => {
      const { cx, cy } = centerOf(points);
      const coords: SpotCoordinates = { points, center_x: cx, center_y: cy };
      return spotApi.updateCoordinates(activeSpotId as number, { spot_coordinates: coords });
    },
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["spotsByParking", effectiveParkingId] });
      await qc.invalidateQueries({ queryKey: ["spotDetail", activeSpotId] });
      resetEditor();
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => spotApi.delete(id),
    onSuccess: async () => {
      await qc.invalidateQueries({ queryKey: ["spotsByParking", effectiveParkingId] });
      if (activeSpotId) setActiveSpotId(null);
    },
  });

  const resetEditor = () => {
    setMode("idle");
    setActiveSpotId(null);
    setSpotNumber("");
    setSpotType("STANDARD");
    setPoints([]);
  };

  const canSave = points.length === 4 && spotNumber.trim().length >= 1;

  return (
    <div className="flex flex-col h-full">
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-7 h-7 bg-blue-600 rounded-md flex items-center justify-center">
            <ParkingSquare className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-gray-900 text-sm">
            Разметка мест (parking-management)
          </span>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        <div className="w-80 bg-white border-r border-gray-200 flex flex-col overflow-y-auto">
          <div className="p-4 space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Парковка
              </label>
              <select
                value={effectiveParkingId ?? ""}
                disabled={parkings.length === 0}
                onChange={(e) => setParkingId(Number(e.target.value))}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {parkings.map((p: ParkingRead) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="border-t border-gray-100 pt-3">
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Фон (локально, опционально)
              </label>
              <input
                type="file"
                accept="image/*"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (!f) return;
                  const r = new FileReader();
                  r.onload = () => setBgImage(String(r.result));
                  r.readAsDataURL(f);
                }}
              />
            </div>

            <div className="border-t border-gray-100 pt-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-gray-900">
                  Места ({spots.length})
                </p>
                <button
                  onClick={() => {
                    resetEditor();
                    setMode("create");
                  }}
                  disabled={effectiveParkingId == null}
                  className="flex items-center space-x-2 px-3 py-1.5 bg-blue-600 text-white text-xs font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Добавить</span>
                </button>
              </div>

              <div className="mt-2 space-y-1 max-h-64 overflow-y-auto">
                {spots.map((s: SpotReadShort) => (
                  <button
                    key={s.id}
                    onClick={() => {
                      setActiveSpotId(s.id);
                      setMode("edit");
                    }}
                    className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm border transition-colors ${
                      activeSpotId === s.id
                        ? "bg-blue-50 text-blue-700 border-blue-200"
                        : "hover:bg-gray-50 text-gray-700 border-gray-100"
                    }`}
                  >
                    <span className="font-medium">{s.spot_number}</span>
                    <span className="text-xs text-gray-500">{s.spot_status}</span>
                  </button>
                ))}
                {spots.length === 0 && (
                  <p className="text-sm text-gray-500 mt-2">
                    Пока нет мест — добавь первое.
                  </p>
                )}
              </div>
            </div>

            {(mode === "create" || mode === "edit") && (
              <div className="border-t border-gray-100 pt-3 space-y-2">
                <p className="text-sm font-semibold text-gray-900">
                  {mode === "create" ? "Новое место" : "Редактирование"}
                </p>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Номер места *
                  </label>
                  <input
                    value={spotNumber}
                    onChange={(e) => setSpotNumber(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    placeholder="A-01"
                    disabled={mode === "edit"}
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Тип
                  </label>
                  <select
                    value={spotType}
                    onChange={(e) => setSpotType(e.target.value as SpotType)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    disabled={mode === "edit"}
                  >
                    <option value="STANDARD">STANDARD</option>
                    <option value="DISABLED">DISABLED</option>
                    <option value="EV">EV</option>
                    <option value="MOTORCYCLE">MOTORCYCLE</option>
                  </select>
                </div>
                <p className="text-xs text-gray-500">
                  Кликни 4 точки на схеме (по часовой стрелке). Сейчас:{" "}
                  <strong>{points.length}/4</strong>
                </p>
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setPoints([])}
                    className="px-3 py-2 text-xs border border-gray-300 rounded-lg hover:bg-gray-50"
                  >
                    Сбросить точки
                  </button>
                  {mode === "edit" && activeSpotId != null && (
                    <button
                      onClick={() => {
                        if (confirm("Удалить место?")) deleteMutation.mutate(activeSpotId);
                      }}
                      className="px-3 py-2 text-xs border border-red-200 text-red-600 bg-red-50 rounded-lg hover:bg-red-100"
                    >
                      <Trash2 className="inline w-3.5 h-3.5 mr-1" />
                      Удалить
                    </button>
                  )}
                </div>
                <button
                  onClick={() => (mode === "create" ? createMutation.mutate() : updateMutation.mutate())}
                  disabled={!canSave}
                  className="w-full flex items-center justify-center space-x-2 px-3 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  <Check className="w-4 h-4" />
                  <span>{mode === "create" ? "Сохранить место" : "Сохранить разметку"}</span>
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="flex-1 bg-gray-100">
          <MarkerCanvas
            bgImage={bgImage}
            points={points}
            setPoints={setPoints}
            enabled={mode === "create" || mode === "edit"}
          />
        </div>
      </div>
    </div>
  );
}

function MarkerCanvas({
  bgImage,
  points,
  setPoints,
  enabled,
}: {
  bgImage: string | null;
  points: number[][];
  setPoints: (p: number[][]) => void;
  enabled: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 800, height: 600 });

  useEffect(() => {
    const update = () => {
      if (!containerRef.current) return;
      const { width, height } = containerRef.current.getBoundingClientRect();
      setCanvasSize({ width, height });
    };
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d")!;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#F3F4F6";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (bgImage) {
      const img = new Image();
      img.onload = () => {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
        drawOverlay(ctx, points);
      };
      img.src = bgImage;
    } else {
      drawOverlay(ctx, points);
    }
  }, [bgImage, points, canvasSize]);

  const handleClick = (e: React.MouseEvent) => {
    if (!enabled) return;
    if (points.length >= 4) return;
    const rect = canvasRef.current!.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    setPoints([...points, [x, y]]);
  };

  return (
    <div ref={containerRef} className="w-full h-full">
      <canvas
        ref={canvasRef}
        width={canvasSize.width}
        height={canvasSize.height}
        onClick={handleClick}
        className={`w-full h-full ${enabled ? "cursor-crosshair" : "cursor-default"}`}
      />
    </div>
  );
}

function drawOverlay(ctx: CanvasRenderingContext2D, points: number[][]) {
  // точки
  points.forEach((p, idx) => {
    ctx.beginPath();
    ctx.arc(p[0], p[1], 6, 0, Math.PI * 2);
    ctx.fillStyle = "#2563EB";
    ctx.fill();
    ctx.strokeStyle = "white";
    ctx.lineWidth = 2;
    ctx.stroke();
    ctx.fillStyle = "white";
    ctx.font = "bold 10px Inter,sans-serif";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(String(idx + 1), p[0], p[1]);
  });

  // полигон
  if (points.length >= 2) {
    ctx.beginPath();
    points.forEach((p, i) => {
      if (i === 0) ctx.moveTo(p[0], p[1]);
      else ctx.lineTo(p[0], p[1]);
    });
    if (points.length === 4) ctx.closePath();
    ctx.strokeStyle = "#2563EB";
    ctx.lineWidth = 2;
    ctx.stroke();
    if (points.length === 4) {
      ctx.fillStyle = "rgba(37,99,235,0.10)";
      ctx.fill();
    }
  }
}
