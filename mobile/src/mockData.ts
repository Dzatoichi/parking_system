import { Booking, Parking, ParkingSpot, Vehicle } from "./types";

export const demoParkings: Parking[] = [
  {
    id: 1,
    name: "Паркинг ЖК Северный",
    address: "Красноярск, ул. Алексеева, 24",
    capacity: 64,
    latitude: 56.049,
    longitude: 92.903
  },
  {
    id: 2,
    name: "Бизнес-центр Енисей",
    address: "Красноярск, пр. Мира, 91",
    capacity: 38,
    latitude: 56.011,
    longitude: 92.852
  }
];

export const demoSpots: ParkingSpot[] = Array.from({ length: 24 }, (_, index) => {
  const id = index + 1;
  const reserved = [3, 7, 11, 18].includes(id);
  const disabled = [5, 6].includes(id);
  return {
    id,
    name: `${id.toString().padStart(3, "0")}`,
    parking_id: 1,
    hourly_rate: disabled ? 90 : 120,
    for_disabled: disabled,
    status: reserved ? 2 : 1
  };
});

export const demoVehicles: Vehicle[] = [
  { id: 1, number_plate: "А123ВС124", name: "Основной автомобиль" }
];

export const demoBooking: Booking = {
  id: 101,
  start_time: new Date(Date.now() + 15 * 60_000).toISOString(),
  end_time: new Date(Date.now() + 2 * 60 * 60_000).toISOString(),
  status: 2,
  parking_id: 1,
  parking_spot: 12,
  parking_spot_id: 12,
  spot_name: "012",
  hourly_rate: 120,
  total_cost: 240
};
