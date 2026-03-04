import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  Upload, Plus, Trash2, Square, MousePointer, Car, RotateCcw, CheckCircle, AlertCircle, ChevronDown, ChevronRight,
  ParkingSquare, Layers, Grid, Eye, EyeOff, XCircle,
} from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { markerAPI } from '../../services/markerApi';

interface Container { points: { x: number; y: number }[] }
interface CarDimensions { length: number; width: number; height: number }
interface AppState { image_loaded: boolean; containers_count: number; cars_count: number; active_container: number | null }

const CAR_PRESETS: Record<string, CarDimensions> = {
  compact: { length: 4.0, width: 1.7, height: 1.5 },
  sedan: { length: 4.8, width: 1.8, height: 1.5 },
  suv: { length: 4.8, width: 1.9, height: 1.7 },
  truck: { length: 5.5, width: 2.0, height: 1.9 },
};

const CAR_PRESET_LABELS: Record<string, string> = {
  compact: 'Компактный',
  sedan: 'Седан',
  suv: 'Внедорожник',
  truck: 'Грузовик',
};

export function ParkingMarker() {
  const [imageSrc, setImageSrc] = useState<string | null>(null);
  const [imageDimensions, setImageDimensions] = useState({ width: 0, height: 0 });
  const [containers, setContainers] = useState<Container[]>([]);
  const [activeContainerIndex, setActiveContainerIndex] = useState<number | null>(null);
  const [carBboxes, setCarBboxes] = useState<{ x1: number; y1: number; x2: number; y2: number }[]>([]);
  const [selectedCarIndex, setSelectedCarIndex] = useState<number | null>(null);
  const [carType, setCarType] = useState('sedan');
  const [carDimensions, setCarDimensions] = useState<CarDimensions>(CAR_PRESETS.sedan);
  const [drawingCarBbox, setDrawingCarBbox] = useState(false);
  const [loading, setLoading] = useState(false);
  const [appState, setAppState] = useState<AppState>({ image_loaded: false, containers_count: 0, cars_count: 0, active_container: null });
  const [toast, setToast] = useState<{ msg: string; type: 'success' | 'error' | 'info' | 'warning' } | null>(null);
  const [openSection, setOpenSection] = useState<string>('containers');
  const [containerParams, setContainerParams] = useState({ length: 6.0, width: 2.5, height: 2.0 });

  const showToast = (msg: string, type: 'success' | 'error' | 'info' | 'warning' = 'info') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3500);
  };

  const updateState = async () => {
    try {
      const state = await markerAPI.getState() as AppState;
      setAppState(state);
    } catch {}
  };

  const updateImage = async () => {
    try {
      const res = await markerAPI.getImage() as any;
      if (res?.success && res.image_base64) {
        setImageSrc(`data:image/png;base64,${res.image_base64}`);
        if (res.width && res.height) setImageDimensions({ width: res.width, height: res.height });
      }
    } catch {}
  };

  useEffect(() => { updateState(); }, []);
  useEffect(() => { if (appState.image_loaded) updateImage(); }, [appState.image_loaded]);

  const handleImageLoad = async (file: File) => {
    setLoading(true);
    try {
      const res = await markerAPI.uploadImage(file) as any;
      if (res?.success) {
        setImageSrc(`data:image/png;base64,${res.image_base64}`);
        setImageDimensions({ width: res.width, height: res.height });
        setContainers([]);
        setCarBboxes([]);
        setActiveContainerIndex(null);
        showToast('Изображение загружено', 'success');
        await updateState();
      }
    } catch (e: any) {
      showToast('Ошибка загрузки изображения', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleAddContainer = async () => {
    setLoading(true);
    try {
      await markerAPI.addContainer();
      const idx = containers.length;
      setContainers((prev) => [...prev, { points: [] }]);
      setActiveContainerIndex(idx);
      await updateState();
      await updateImage();
      showToast('Контейнер добавлен', 'success');
    } catch {
      showToast('Ошибка добавления контейнера', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleCanvasClick = async (x: number, y: number) => {
    if (activeContainerIndex === null) { showToast('Сначала выберите контейнер', 'warning'); return; }
    setContainers((prev) => prev.map((c, i) => i === activeContainerIndex ? { ...c, points: [...(c.points ?? []), { x, y }] } : c));
    try {
      await markerAPI.addPoint(x, y);
      await updateImage();
      await updateState();
    } catch {
      showToast('Ошибка добавления точки', 'error');
    }
  };

  const handleSelectContainer = async (index: number) => {
    try {
      await markerAPI.setActiveContainer(index);
      setActiveContainerIndex(index);
      await updateState();
    } catch {
      showToast('Ошибка выбора контейнера', 'error');
    }
  };

  const handleFinishCarSelection = async (x1: number, y1: number, x2: number, y2: number) => {
    if (Math.abs(x2 - x1) < 10 || Math.abs(y2 - y1) < 10) { showToast('Слишком маленькая область', 'warning'); return; }
    try {
      await markerAPI.addCarBbox(x1, y1, x2, y2, activeContainerIndex ?? 0);
      await updateImage();
      await updateState();
      setCarBboxes((prev) => [...prev, { x1, y1, x2, y2 }]);
      showToast('Автомобиль добавлен', 'success');
    } catch {
      showToast('Ошибка добавления автомобиля', 'error');
    }
    setDrawingCarBbox(false);
  };

  const handleClearAll = async () => {
    if (!confirm('Очистить все данные?')) return;
    try {
      await markerAPI.clearAll();
      setImageSrc(null);
      setContainers([]);
      setCarBboxes([]);
      setActiveContainerIndex(null);
      await updateState();
      showToast('Всё очищено', 'success');
    } catch {
      showToast('Ошибка очистки', 'error');
    }
  };

  const handleCarTypeChange = (type: string) => {
    setCarType(type);
    setCarDimensions(CAR_PRESETS[type] ?? CAR_PRESETS.sedan);
  };

  const containerPoints = containers.map((c, i) => ({ points: c.points ?? [], isActive: i === activeContainerIndex }));
  const carsList = carBboxes.map((b, i) => ({ ...b, isSelected: i === selectedCarIndex }));

  return (
    <div className="flex flex-col h-full relative">
      {/* Toast */}
      {toast && (
        <div className={`fixed top-4 right-4 z-50 flex items-center space-x-2 px-4 py-3 rounded-lg shadow-lg text-sm font-medium transition-all ${
          toast.type === 'success' ? 'bg-green-600 text-white' :
          toast.type === 'error' ? 'bg-red-600 text-white' :
          toast.type === 'warning' ? 'bg-yellow-500 text-white' : 'bg-blue-600 text-white'
        }`}>
          {toast.type === 'success' && <CheckCircle className="w-4 h-4" />}
          {toast.type === 'error' && <XCircle className="w-4 h-4" />}
          {toast.type === 'warning' && <AlertCircle className="w-4 h-4" />}
          {toast.type === 'info' && <AlertCircle className="w-4 h-4" />}
          <span>{toast.msg}</span>
        </div>
      )}

      {/* Sub-header */}
      <div className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="w-7 h-7 bg-blue-600 rounded-md flex items-center justify-center">
            <ParkingSquare className="w-4 h-4 text-white" />
          </div>
          <span className="font-semibold text-gray-900 text-sm">Разметка парковочных мест</span>
        </div>
        <div className="flex items-center space-x-3 text-xs text-gray-500">
          <span>Контейнеров: <strong className="text-gray-800">{appState.containers_count}</strong></span>
          <span>•</span>
          <span>Автомобилей: <strong className="text-gray-800">{appState.cars_count}</strong></span>
          {appState.active_container !== null && (
            <>
              <span>•</span>
              <span>Активный: <strong className="text-blue-600">{appState.active_container + 1}</strong></span>
            </>
          )}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Left panel */}
        <div className="w-72 bg-white border-r border-gray-200 flex flex-col overflow-y-auto">
          {/* Garage params */}
          <AccordionSection title="Параметры парковки" icon={Grid} id="garage" open={openSection} setOpen={setOpenSection}>
            <div className="space-y-2 p-3">
              {(['length', 'width', 'height'] as const).map((key) => (
                <div key={key}>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    {key === 'length' ? 'Длина (м)' : key === 'width' ? 'Ширина (м)' : 'Высота (м)'}
                  </label>
                  <input type="number" step="0.1" value={containerParams[key]}
                    onChange={(e) => setContainerParams((p) => ({ ...p, [key]: parseFloat(e.target.value) }))}
                    className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              ))}
            </div>
          </AccordionSection>

          {/* Containers */}
          <AccordionSection title={`Контейнеры (${containers.length})`} icon={Layers} id="containers" open={openSection} setOpen={setOpenSection}>
            <div className="p-3 space-y-2">
              <button onClick={handleAddContainer} disabled={!appState.image_loaded || loading}
                className="w-full flex items-center justify-center space-x-2 py-2 px-3 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
                <Plus className="w-4 h-4" />
                <span>Добавить контейнер</span>
              </button>
              {containers.length > 0 && (
                <div className="space-y-1 max-h-48 overflow-y-auto">
                  {containers.map((c, i) => (
                    <button key={i} onClick={() => handleSelectContainer(i)}
                      className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-colors ${
                        i === activeContainerIndex ? 'bg-blue-50 text-blue-700 border border-blue-200' : 'hover:bg-gray-50 text-gray-700'
                      }`}>
                      <span className="font-medium">Контейнер {i + 1}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded-full ${(c.points?.length ?? 0) >= 4 ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                        {c.points?.length ?? 0}/4
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </AccordionSection>

          {/* Car selection */}
          <AccordionSection title="Транспорт" icon={Car} id="cars" open={openSection} setOpen={setOpenSection}>
            <div className="p-3 space-y-2">
              <div>
                <label className="block text-xs font-medium text-gray-600 mb-1">Тип авто</label>
                <select value={carType} onChange={(e) => handleCarTypeChange(e.target.value)}
                  className="w-full px-3 py-1.5 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {Object.keys(CAR_PRESETS).map((k) => (
                    <option key={k} value={k}>{CAR_PRESET_LABELS[k]} — {CAR_PRESETS[k].length}×{CAR_PRESETS[k].width}×{CAR_PRESETS[k].height}м</option>
                  ))}
                </select>
              </div>
              <button
                onClick={() => { if (activeContainerIndex === null) { showToast('Выберите контейнер', 'warning'); return; } setDrawingCarBbox(true); showToast('Выделите автомобиль на изображении', 'info'); }}
                disabled={!appState.image_loaded}
                className={`w-full flex items-center justify-center space-x-2 py-2 px-3 text-sm font-medium rounded-lg transition-colors ${
                  drawingCarBbox ? 'bg-orange-500 text-white hover:bg-orange-600' : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                } disabled:opacity-50`}>
                <Square className="w-4 h-4" />
                <span>{drawingCarBbox ? 'Выделяем...' : 'Выделить авто'}</span>
              </button>
              {carBboxes.length > 0 && (
                <div className="text-xs text-gray-500 text-center">Добавлено: {carBboxes.length} авт.</div>
              )}
            </div>
          </AccordionSection>

          {/* Actions */}
          <div className="p-3 mt-auto border-t border-gray-200">
            <button onClick={handleClearAll} disabled={!appState.image_loaded}
              className="w-full flex items-center justify-center space-x-2 py-2 px-3 text-sm font-medium text-red-600 border border-red-200 bg-red-50 rounded-lg hover:bg-red-100 disabled:opacity-50 transition-colors">
              <RotateCcw className="w-4 h-4" />
              <span>Очистить всё</span>
            </button>
          </div>
        </div>

        {/* Canvas area */}
        <div className="flex-1 overflow-hidden">
          <MarkerCanvas
            imageSrc={imageSrc}
            onImageLoad={handleImageLoad}
            onCanvasClick={handleCanvasClick}
            onBboxEnd={handleFinishCarSelection}
            drawingBbox={drawingCarBbox}
            containerPoints={containerPoints}
            carBboxes={carsList}
            imageDimensions={imageDimensions}
            loading={loading}
          />
        </div>
      </div>
    </div>
  );
}

// ─── AccordionSection ─────────────────────────────────────────────────────────
function AccordionSection({ title, icon: Icon, id, open, setOpen, children }: {
  title: string; icon: React.ElementType; id: string; open: string; setOpen: (v: string) => void; children: React.ReactNode;
}) {
  const isOpen = open === id;
  return (
    <div className="border-b border-gray-100">
      <button onClick={() => setOpen(isOpen ? '' : id)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-50 transition-colors">
        <div className="flex items-center space-x-2 text-sm font-medium text-gray-700">
          <Icon className="w-4 h-4 text-gray-500" />
          <span>{title}</span>
        </div>
        {isOpen ? <ChevronDown className="w-4 h-4 text-gray-400" /> : <ChevronRight className="w-4 h-4 text-gray-400" />}
      </button>
      {isOpen && <div className="border-t border-gray-100">{children}</div>}
    </div>
  );
}

// ─── MarkerCanvas ─────────────────────────────────────────────────────────────
function MarkerCanvas({
  imageSrc, onImageLoad, onCanvasClick, onBboxEnd, drawingBbox, containerPoints, carBboxes, imageDimensions, loading,
}: {
  imageSrc: string | null;
  onImageLoad: (f: File) => void;
  onCanvasClick: (x: number, y: number) => void;
  onBboxEnd: (x1: number, y1: number, x2: number, y2: number) => void;
  drawingBbox: boolean;
  containerPoints: { points: { x: number; y: number }[]; isActive: boolean }[];
  carBboxes: { x1: number; y1: number; x2: number; y2: number; isSelected?: boolean }[];
  imageDimensions: { width: number; height: number };
  loading: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [canvasSize, setCanvasSize] = useState({ width: 800, height: 600 });
  const [scale, setScale] = useState({ x: 1, y: 1 });
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const [dragEnd, setDragEnd] = useState<{ x: number; y: number } | null>(null);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: { 'image/*': ['.jpeg', '.jpg', '.png', '.bmp', '.tiff'] },
    onDrop: (files) => files[0] && onImageLoad(files[0]),
    noClick: !!imageSrc,
  });

  useEffect(() => {
    const update = () => {
      if (!containerRef.current) return;
      const { width, height } = containerRef.current.getBoundingClientRect();
      setCanvasSize({ width, height });
    };
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !imageSrc) return;
    const ctx = canvas.getContext('2d')!;
    const img = new Image();
    img.onload = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const imgRatio = img.width / img.height;
      const canvasRatio = canvas.width / canvas.height;
      let drawWidth, drawHeight, ox = 0, oy = 0;
      if (imgRatio > canvasRatio) { drawWidth = canvas.width; drawHeight = canvas.width / imgRatio; oy = (canvas.height - drawHeight) / 2; }
      else { drawHeight = canvas.height; drawWidth = canvas.height * imgRatio; ox = (canvas.width - drawWidth) / 2; }
      const sx = drawWidth / img.width, sy = drawHeight / img.height;
      setScale({ x: sx, y: sy }); setOffset({ x: ox, y: oy });
      ctx.drawImage(img, ox, oy, drawWidth, drawHeight);

      // Containers
      containerPoints.forEach((con, ci) => {
        if (con.points.length >= 2) {
          ctx.beginPath();
          con.points.forEach((p, pi) => {
            const cx = ox + p.x * sx, cy = oy + p.y * sy;
            pi === 0 ? ctx.moveTo(cx, cy) : ctx.lineTo(cx, cy);
          });
          if (con.points.length === 4) ctx.closePath();
          ctx.strokeStyle = con.isActive ? '#2563EB' : '#9CA3AF';
          ctx.lineWidth = con.isActive ? 2.5 : 1.5;
          ctx.setLineDash(con.isActive ? [] : [4, 4]);
          ctx.stroke();
          ctx.setLineDash([]);
          if (con.points.length === 4) {
            ctx.fillStyle = con.isActive ? 'rgba(37,99,235,0.08)' : 'rgba(156,163,175,0.1)';
            ctx.fill();
          }
        }
        con.points.forEach((p, pi) => {
          const cx = ox + p.x * sx, cy = oy + p.y * sy;
          ctx.beginPath(); ctx.arc(cx, cy, 6, 0, Math.PI * 2);
          ctx.fillStyle = con.isActive ? '#2563EB' : '#6B7280'; ctx.fill();
          ctx.strokeStyle = 'white'; ctx.lineWidth = 2; ctx.stroke();
          ctx.fillStyle = 'white'; ctx.font = 'bold 10px Inter,sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
          ctx.fillText(String(pi + 1), cx, cy);
        });
      });

      // Car bboxes
      carBboxes.forEach((b, i) => {
        const bx1 = ox + b.x1 * sx, by1 = oy + b.y1 * sy, bx2 = ox + b.x2 * sx, by2 = oy + b.y2 * sy;
        ctx.strokeStyle = b.isSelected ? '#F59E0B' : '#EF4444';
        ctx.lineWidth = b.isSelected ? 2.5 : 1.5;
        ctx.strokeRect(bx1, by1, bx2 - bx1, by2 - by1);
        ctx.fillStyle = b.isSelected ? 'rgba(245,158,11,0.1)' : 'rgba(239,68,68,0.08)';
        ctx.fillRect(bx1, by1, bx2 - bx1, by2 - by1);
        ctx.fillStyle = b.isSelected ? '#F59E0B' : '#EF4444';
        ctx.font = 'bold 11px Inter,sans-serif'; ctx.textAlign = 'left'; ctx.textBaseline = 'bottom';
        ctx.fillText(`Авто ${i + 1}`, bx1 + 2, by1 - 2);
      });

      // Drawing bbox
      if (drawingBbox && dragStart && dragEnd) {
        ctx.strokeStyle = '#F59E0B'; ctx.lineWidth = 2;
        ctx.setLineDash([5, 5]);
        ctx.strokeRect(dragStart.x, dragStart.y, dragEnd.x - dragStart.x, dragEnd.y - dragStart.y);
        ctx.setLineDash([]);
        ctx.fillStyle = 'rgba(245,158,11,0.1)';
        ctx.fillRect(dragStart.x, dragStart.y, dragEnd.x - dragStart.x, dragEnd.y - dragStart.y);
      }
    };
    img.src = imageSrc;
  }, [imageSrc, containerPoints, carBboxes, drawingBbox, dragStart, dragEnd, canvasSize]);

  const handleMouseDown = (e: React.MouseEvent) => {
    if (!imageSrc) return;
    const rect = canvasRef.current!.getBoundingClientRect();
    const x = e.clientX - rect.left, y = e.clientY - rect.top;
    if (drawingBbox) { setIsDragging(true); setDragStart({ x, y }); setDragEnd({ x, y }); }
    else {
      const imgX = (x - offset.x) / scale.x, imgY = (y - offset.y) / scale.y;
      if (imgX >= 0 && imgY >= 0 && imgX <= imageDimensions.width && imgY <= imageDimensions.height) onCanvasClick(imgX, imgY);
    }
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDragging) return;
    const rect = canvasRef.current!.getBoundingClientRect();
    setDragEnd({ x: e.clientX - rect.left, y: e.clientY - rect.top });
  };

  const handleMouseUp = () => {
    if (isDragging && dragStart && dragEnd && drawingBbox) {
      const x1 = (Math.min(dragStart.x, dragEnd.x) - offset.x) / scale.x;
      const y1 = (Math.min(dragStart.y, dragEnd.y) - offset.y) / scale.y;
      const x2 = (Math.max(dragStart.x, dragEnd.x) - offset.x) / scale.x;
      const y2 = (Math.max(dragStart.y, dragEnd.y) - offset.y) / scale.y;
      onBboxEnd(x1, y1, x2, y2);
    }
    setIsDragging(false); setDragStart(null); setDragEnd(null);
  };

  if (loading) {
    return (
      <div className="w-full h-full flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-10 h-10 border-2 border-gray-300 border-t-blue-600 rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-gray-500">Обработка...</p>
        </div>
      </div>
    );
  }

  if (!imageSrc) {
    return (
      <div ref={containerRef} {...getRootProps()} className="w-full h-full flex items-center justify-center cursor-pointer">
        <input {...getInputProps()} />
        <div className={`text-center p-12 rounded-2xl border-2 border-dashed transition-colors ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-gray-300 bg-gray-50 hover:border-blue-400 hover:bg-blue-50/50'}`}>
          <div className="w-16 h-16 bg-blue-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <Upload className="w-8 h-8 text-blue-600" />
          </div>
          <p className="text-lg font-semibold text-gray-800">{isDragActive ? 'Отпустите файл' : 'Загрузите изображение'}</p>
          <p className="text-sm text-gray-500 mt-2">Перетащите файл или нажмите для выбора</p>
          <p className="text-xs text-gray-400 mt-1">JPG, PNG, BMP, TIFF</p>
        </div>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="w-full h-full relative bg-gray-100">
      <canvas
        ref={canvasRef}
        width={canvasSize.width}
        height={canvasSize.height}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        className={`w-full h-full ${drawingBbox ? 'cursor-crosshair' : 'cursor-crosshair'}`}
      />
      {drawingBbox && (
        <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-orange-500 text-white text-xs font-medium px-3 py-1.5 rounded-full shadow">
          Выделяйте автомобиль мышью
        </div>
      )}
    </div>
  );
}
