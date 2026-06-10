import React, { useState } from "react";
import { ChevronLeft, ChevronRight, RotateCcw } from "lucide-react";
import { useBookingsData } from "../hooks/useBookingsData";
import type { BookingStatus } from "../services/pmApi";

const statusColors: Record<BookingStatus, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  confirmed: "bg-blue-100 text-blue-800",
  completed: "bg-green-100 text-green-800",
  cancelled: "bg-gray-100 text-gray-800",
  expired: "bg-red-100 text-red-800",
};

const statusLabels: Record<BookingStatus, string> = {
  pending: "Ожидает",
  confirmed: "Подтвержден",
  completed: "Завершен",
  cancelled: "Отменен",
  expired: "Истек",
};

function formatDateTime(value: string) {
  return new Date(value).toLocaleString("ru-RU");
}

export function Bookings() {
  const [status, setStatus] = useState<BookingStatus | "">("");
  const [vehiclePlate, setVehiclePlate] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const { data, loading, error } = useBookingsData({
    status: status || undefined,
    vehiclePlate: vehiclePlate.trim() || undefined,
    startDate: startDate || undefined,
    endDate: endDate || undefined,
    page,
    size: pageSize,
  });

  const resetPage = () => setPage(1);

  const handleStatusChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setStatus(e.target.value as BookingStatus | "");
    resetPage();
  };

  const resetFilters = () => {
    setStatus("");
    setVehiclePlate("");
    setStartDate("");
    setEndDate("");
    resetPage();
  };

  const handlePreviousPage = () => {
    setPage((current) => Math.max(current - 1, 1));
  };

  const handleNextPage = () => {
    if (data && page < Math.ceil(data.total / pageSize)) {
      setPage((current) => current + 1);
    }
  };

  const totalPages = data ? Math.ceil(data.total / pageSize) : 0;

  return (
    <div className="h-full flex flex-col bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-2xl font-semibold text-gray-900">Журнал бронирований</h1>
      </div>

      <div className="p-6">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Статус
              </label>
              <select
                value={status}
                onChange={handleStatusChange}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Все</option>
                <option value="pending">Ожидает</option>
                <option value="confirmed">Подтвержден</option>
                <option value="completed">Завершен</option>
                <option value="cancelled">Отменен</option>
                <option value="expired">Истек</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Госномер авто
              </label>
              <input
                type="text"
                value={vehiclePlate}
                onChange={(event) => {
                  setVehiclePlate(event.target.value.toUpperCase());
                  resetPage();
                }}
                placeholder="A123BC77"
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Дата начала
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(event) => {
                  setStartDate(event.target.value);
                  resetPage();
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Дата конца
              </label>
              <div className="flex gap-2">
                <input
                  type="date"
                  value={endDate}
                  onChange={(event) => {
                    setEndDate(event.target.value);
                    resetPage();
                  }}
                  className="min-w-0 flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                />
                <button
                  type="button"
                  onClick={resetFilters}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-gray-300 bg-white text-gray-700 hover:bg-gray-50"
                  title="Сбросить фильтры"
                  aria-label="Сбросить фильтры"
                >
                  <RotateCcw className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        </div>

        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Место
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Пользователь
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Авто
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Начало
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Конец
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Статус
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Создано
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {loading && (
                  <tr>
                    <td colSpan={8} className="px-6 py-8 text-center text-gray-500">
                      Загрузка...
                    </td>
                  </tr>
                )}

                {error && (
                  <tr>
                    <td colSpan={8} className="px-6 py-8 text-center text-red-600">
                      Ошибка загрузки данных: {error}
                    </td>
                  </tr>
                )}

                {!loading && !error && data?.items.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-6 py-8 text-center text-gray-500">
                      Нет данных
                    </td>
                  </tr>
                )}

                {!loading &&
                  !error &&
                  data?.items.map((booking) => (
                    <tr key={booking.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {booking.id}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {booking.spot_number ?? `ID ${booking.spot_id}`}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {booking.user_name ?? `ID ${booking.user_id}`}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {booking.vehicle_plate_number ?? "-"}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatDateTime(booking.start_time)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {formatDateTime(booking.end_time)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span
                          className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${statusColors[booking.status]}`}
                        >
                          {statusLabels[booking.status]}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDateTime(booking.created_at)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>

          {data && data.total > 0 && (
            <div className="px-6 py-4 border-t border-gray-200 flex items-center justify-between">
              <div className="text-sm text-gray-700">
                Страница {page} из {totalPages}
              </div>
              <div className="flex space-x-2">
                <button
                  onClick={handlePreviousPage}
                  disabled={page === 1}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <ChevronLeft className="w-4 h-4 mr-1" />
                  Назад
                </button>
                <button
                  onClick={handleNextPage}
                  disabled={page >= totalPages}
                  className="inline-flex items-center px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Вперед
                  <ChevronRight className="w-4 h-4 ml-1" />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
