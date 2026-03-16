import { useState, useEffect, useCallback } from "react";
import { spotApi, parkingApi } from "../services/pmApi";
import type { ParkingStats, ParkingRead } from "../services/pmApi";

const POLL_INTERVAL_MS = 30_000;

interface UseParkingStatsResult {
  stats: ParkingStats | null;
  parking: ParkingRead | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useParkingStats(parkingId: number | null): UseParkingStatsResult {
  const [stats, setStats] = useState<ParkingStats | null>(null);
  const [parking, setParking] = useState<ParkingRead | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = useCallback(async () => {
    if (parkingId === null) return;
    setLoading(true);
    setError(null);
    try {
      const [statsRes, parkingRes] = await Promise.all([
        spotApi.getStats(parkingId),
        parkingApi.getAll({ only_active: true, page: 1, size: 50 }),
      ]);
      setStats(statsRes.data);
      const found = parkingRes.data.items.find((p) => p.id === parkingId);
      if (found) setParking(found);
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? "Ошибка загрузки данных");
    } finally {
      setLoading(false);
    }
  }, [parkingId]);

  // Первый запрос
  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  // Polling каждые 30 секунд
  useEffect(() => {
    if (parkingId === null) return;
    const timer = setInterval(fetchStats, POLL_INTERVAL_MS);
    return () => clearInterval(timer);
  }, [fetchStats, parkingId]);

  return { stats, parking, loading, error, refetch: fetchStats };
}

// Хук для автоматического получения первой активной парковки
export function useFirstParking() {
  const [parkingId, setParkingId] = useState<number | null>(null);

  useEffect(() => {
    parkingApi
      .getAll({ only_active: true, page: 1, size: 1 })
      .then((res) => {
        const first = res.data.items[0];
        if (first) setParkingId(first.id);
      })
      .catch(() => {
        // Если API недоступен — оставляем null
      });
  }, []);

  return parkingId;
}