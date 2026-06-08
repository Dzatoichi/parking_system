export type BookingTimeSlot = {
  startTime: Date;
  endTime: Date;
};

export type BookingTimeField = "start" | "end";

export type BookingDateTimeInput = {
  date: string;
  startHour: string;
  startMinute: string;
  endHour: string;
  endMinute: string;
};

export const bookingDurationOptions = [1, 2, 3, 4] as const;
export type BookingDurationHours = (typeof bookingDurationOptions)[number];

const defaultLeadMinutes = 15;
const minuteMs = 60_000;
const hourMs = 60 * minuteMs;

export function createDefaultBookingTimeSlot(now = new Date()): BookingTimeSlot {
  const startTime = roundUpToNextQuarter(new Date(now.getTime() + defaultLeadMinutes * minuteMs));
  return {
    startTime,
    endTime: new Date(startTime.getTime() + 2 * hourMs)
  };
}

export function createBookingDateTimeInput(slot: BookingTimeSlot): BookingDateTimeInput {
  return {
    date: formatDateInput(slot.startTime),
    startHour: pad2(slot.startTime.getHours()),
    startMinute: pad2(slot.startTime.getMinutes()),
    endHour: pad2(slot.endTime.getHours()),
    endMinute: pad2(slot.endTime.getMinutes())
  };
}

export function parseBookingDateTimeInput(input: BookingDateTimeInput): BookingTimeSlot | null {
  const startTime = parseLocalDateTime(input.date, input.startHour, input.startMinute);
  const endTime = parseLocalDateTime(input.date, input.endHour, input.endMinute);
  return startTime && endTime ? { startTime, endTime } : null;
}

export function shiftBookingDay(slot: BookingTimeSlot, days: number): BookingTimeSlot {
  return {
    startTime: addDays(slot.startTime, days),
    endTime: addDays(slot.endTime, days)
  };
}

export function shiftBookingTime(slot: BookingTimeSlot, field: BookingTimeField, minutes: number): BookingTimeSlot {
  if (field === "start") {
    return { ...slot, startTime: new Date(slot.startTime.getTime() + minutes * minuteMs) };
  }
  return { ...slot, endTime: new Date(slot.endTime.getTime() + minutes * minuteMs) };
}

export function shiftBookingStart(slot: BookingTimeSlot, minutes: number): BookingTimeSlot {
  const durationMs = slot.endTime.getTime() - slot.startTime.getTime();
  const startTime = new Date(slot.startTime.getTime() + minutes * minuteMs);
  return {
    startTime,
    endTime: new Date(startTime.getTime() + Math.max(hourMs, durationMs))
  };
}

export function setBookingDuration(slot: BookingTimeSlot, hours: BookingDurationHours): BookingTimeSlot {
  return {
    startTime: slot.startTime,
    endTime: new Date(slot.startTime.getTime() + hours * hourMs)
  };
}

export function setBookingDate(slot: BookingTimeSlot, date: string): BookingTimeSlot {
  const startTime = parseLocalDateTime(date, String(slot.startTime.getHours()), String(slot.startTime.getMinutes()));
  const endTime = parseLocalDateTime(date, String(slot.endTime.getHours()), String(slot.endTime.getMinutes()));
  return startTime && endTime ? { startTime, endTime } : slot;
}

export function setBookingClock(slot: BookingTimeSlot, field: BookingTimeField, hour: string, minute: string): BookingTimeSlot {
  const base = field === "start" ? slot.startTime : slot.endTime;
  const next = parseLocalDateTime(formatDateInput(base), hour, minute);
  if (!next) {
    return slot;
  }
  return field === "start" ? { ...slot, startTime: next } : { ...slot, endTime: next };
}

export function getBookingDurationMinutes(slot: BookingTimeSlot) {
  const durationMs = slot.endTime.getTime() - slot.startTime.getTime();
  return Math.max(0, Math.ceil(durationMs / minuteMs));
}

export function getBookingDurationHours(slot: BookingTimeSlot) {
  const durationMs = slot.endTime.getTime() - slot.startTime.getTime();
  return Math.max(1, Math.ceil(durationMs / hourMs));
}

export function calculateBookingCost(hourlyRate: number, slot: BookingTimeSlot) {
  return Math.round((Math.max(0, hourlyRate) * getBookingDurationMinutes(slot)) / 60);
}

export function validateBookingTimeSlot(slot: BookingTimeSlot, now = new Date()): string | null {
  if (!Number.isFinite(slot.startTime.getTime()) || !Number.isFinite(slot.endTime.getTime())) {
    return "Некорректная дата или время бронирования.";
  }
  if (slot.startTime.getTime() < now.getTime()) {
    return "Время начала бронирования не может быть в прошлом.";
  }
  if (slot.endTime.getTime() <= slot.startTime.getTime()) {
    return "Время окончания должно быть позже времени начала.";
  }
  return null;
}

export function formatBookingDateTime(value: Date | string) {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit"
  }).format(typeof value === "string" ? new Date(value) : value);
}

export function formatBookingDuration(slot: BookingTimeSlot) {
  const minutes = getBookingDurationMinutes(slot);
  const hoursPart = Math.floor(minutes / 60);
  const minutesPart = minutes % 60;
  if (hoursPart === 0) {
    return `${minutesPart} мин`;
  }
  if (minutesPart === 0) {
    return `${hoursPart} ч`;
  }
  return `${hoursPart} ч ${minutesPart} мин`;
}

export function formatDateInput(value: Date) {
  return `${value.getFullYear()}-${pad2(value.getMonth() + 1)}-${pad2(value.getDate())}`;
}

function roundUpToNextQuarter(value: Date) {
  const rounded = new Date(value);
  const minutes = rounded.getMinutes();
  const nextQuarter = Math.ceil(minutes / 15) * 15;
  rounded.setMinutes(nextQuarter, 0, 0);
  return rounded;
}

function addDays(value: Date, days: number) {
  const next = new Date(value);
  next.setDate(next.getDate() + days);
  return next;
}

function parseLocalDateTime(date: string, hour: string, minute: string) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return null;
  }
  const parsedHour = Number(hour);
  const parsedMinute = Number(minute);
  if (!Number.isInteger(parsedHour) || parsedHour < 0 || parsedHour > 23) {
    return null;
  }
  if (!Number.isInteger(parsedMinute) || parsedMinute < 0 || parsedMinute > 59) {
    return null;
  }
  const [year, month, day] = date.split("-").map(Number);
  const result = new Date(year, month - 1, day, parsedHour, parsedMinute, 0, 0);
  return Number.isFinite(result.getTime()) ? result : null;
}

function pad2(value: number) {
  return value.toString().padStart(2, "0");
}
