import { useState, useEffect } from 'react';
import { bookingApi, type BookingStatus, type BookingRead, type PaginatedResponse } from '../services/pmApi';

interface UseBookingsDataParams {
  status?: BookingStatus;
  from?: string;
  to?: string;
  page?: number;
  size?: number;
}

interface UseBookingsDataReturn {
  data: PaginatedResponse<BookingRead> | null;
  loading: boolean;
  error: string | null;
  refetch: () => void;
}

export function useBookingsData({
  status,
  from,
  to,
  page = 1,
  size = 20,
}: UseBookingsDataParams): UseBookingsDataReturn {
  const [data, setData] = useState<PaginatedResponse<BookingRead> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const params: any = {
        page,
        size,
      };

      if (status) params.status = status;
      if (from) params.from = from;
      if (to) params.to = to;

      const response = await bookingApi.getAll(params);
      setData(response.data);
    } catch (err: any) {
      setError(err.message || 'Ошибка загрузки данных');
      console.error('Error fetching bookings:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [status, from, to, page, size]);

  useEffect(() => {
    const interval = setInterval(() => {
      fetchData();
    }, 30000); // 30 seconds

    return () => clearInterval(interval);
  }, [status, from, to, page, size]);

  return { data, loading, error, refetch: fetchData };
}