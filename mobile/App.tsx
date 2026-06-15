import { Ionicons } from "@expo/vector-icons";
import * as ImagePicker from "expo-image-picker";
import { StatusBar } from "expo-status-bar";
import { useEffect, useMemo, useRef, useState } from "react";
import { SafeAreaProvider, SafeAreaView } from "react-native-safe-area-context";
import {
  ActivityIndicator,
  Alert,
  Animated,
  FlatList,
  Image,
  KeyboardAvoidingView,
  Modal,
  PanResponder,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View
} from "react-native";
import {
  addVehicle,
  confirmBookingAfterPayment,
  confirmMockPayment,
  getActiveBooking,
  getApiBaseUrl,
  getErrorMessage,
  cancelBooking,
  createBooking,
  createMockPayment,
  getParkings,
  getOwnerSpotReport,
  getOwnerSpots,
  getSpots,
  getVehicles,
  isUnauthorizedError,
  login,
  registerOwnerSpot,
  register,
  updateOwnerSpot
} from "./src/application/mobileServices";
import {
  BookingTimeSlot,
  calculateBookingCost,
  createDefaultBookingTimeSlot,
  formatBookingDateTime,
  formatBookingDuration,
  formatDateInput,
  setBookingClock,
  setBookingDate,
  shiftBookingDay,
  shiftBookingTime,
  validateBookingTimeSlot
} from "./src/domain/booking/bookingTime";
import { clearStoredSession, loadStoredSession, saveStoredSession, sessionTtlMs } from "./src/application/mobileServices";
import { colors, spacing } from "./src/theme";
import { AuthSession, Booking, OwnerSpotReport, Parking, ParkingSpot, Payment, Vehicle, VehiclePhotos } from "./src/types";

type TabKey = "parkings" | "booking" | "vehicle" | "owner" | "profile";

const tabs: Array<{ key: TabKey; label: string; icon: keyof typeof Ionicons.glyphMap }> = [
  { key: "parkings", label: "Парковки", icon: "map-outline" },
  { key: "booking", label: "Бронирования", icon: "time-outline" },
  { key: "vehicle", label: "Авто", icon: "car-outline" },
  { key: "owner", label: "Места", icon: "business-outline" },
  { key: "profile", label: "Профиль", icon: "person-outline" }
];

export default function App() {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("parkings");
  const [parkings, setParkings] = useState<Parking[]>([]);
  const [spots, setSpots] = useState<ParkingSpot[]>([]);
  const [ownerSpots, setOwnerSpots] = useState<ParkingSpot[]>([]);
  const [ownerReports, setOwnerReports] = useState<Record<number, OwnerSpotReport>>({});
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [selectedParking, setSelectedParking] = useState<Parking | null>(null);
  const [selectedSpot, setSelectedSpot] = useState<ParkingSpot | null>(null);
  const [bookingTimeSlot, setBookingTimeSlot] = useState<BookingTimeSlot>(() => createDefaultBookingTimeSlot());
  const [activeBooking, setActiveBooking] = useState<Booking | null>(null);
  const [activePayment, setActivePayment] = useState<Payment | null>(null);
  const [sessionRestoring, setSessionRestoring] = useState(true);
  const [loading, setLoading] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const token = session?.accessToken;

  useEffect(() => {
    let mounted = true;
    loadStoredSession()
      .then((storedSession) => {
        if (mounted) {
          setSession(storedSession);
        }
      })
      .catch(() => {
        if (mounted) {
          setSession(null);
        }
      })
      .finally(() => {
        if (mounted) {
          setSessionRestoring(false);
        }
      });
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (!session) {
      return;
    }

    void loadInitialData();
  }, [session]);

  useEffect(() => {
    if (!session || !selectedParking) {
      return;
    }

    const intervalId = setInterval(() => {
      getSpots(selectedParking.id, token)
        .then((freshSpots) => setSpots(freshSpots))
        .catch((error) => {
          if (isUnauthorizedError(error)) {
            handleError(error, "Нужно войти заново");
          }
        });
    }, 15_000);

    return () => clearInterval(intervalId);
  }, [session, selectedParking, token]);

  async function applySession(nextSession: AuthSession | null) {
    setSession(nextSession);
    if (nextSession) {
      await saveStoredSession(nextSession);
    } else {
      await clearStoredSession();
    }
  }

  async function loadInitialData() {
    if (!session) {
      return;
    }
    setLoading(true);
    setErrorBanner(null);
    try {
      const [parkingList, vehicleList, currentBooking] = await Promise.all([
        getParkings(token),
        getVehicles(token),
        getActiveBooking(session.userId, token)
      ]);
      setParkings(parkingList);
      setVehicles(vehicleList);
      setActiveBooking(currentBooking);
      setActivePayment(null);
      setOwnerSpots(await getOwnerSpots(token));
      setOwnerReports({});
      const firstParking = parkingList[0] ?? null;
      setSelectedParking(firstParking);
      if (firstParking) {
        setSpots(await getSpots(firstParking.id, token));
      }
    } catch (error) {
      handleError(error, "Не удалось загрузить данные");
    } finally {
      setLoading(false);
    }
  }

  async function selectParking(parking: Parking) {
    setSelectedParking(parking);
    setSelectedSpot(null);
    setLoading(true);
    setErrorBanner(null);
    try {
      setSpots(await getSpots(parking.id, token));
    } catch (error) {
      handleError(error, "Не удалось загрузить места");
    } finally {
      setLoading(false);
    }
  }

  async function bookSelectedSpot() {
    if (!session || !selectedParking || !selectedSpot) {
      Alert.alert("Выберите место", "Сначала выберите парковку и свободное парковочное место.");
      return;
    }

    if (vehicles.length === 0) {
      setSelectedSpot(null);
      setActiveTab("vehicle");
      Alert.alert("Добавьте автомобиль", "Перед бронированием нужно добавить данные автомобиля.");
      return;
    }

    setLoading(true);
    setErrorBanner(null);
    try {
      const bookingTimeError = validateBookingTimeSlot(bookingTimeSlot);
      if (bookingTimeError) {
        Alert.alert("Проверьте время", bookingTimeError);
        return;
      }

      const hourlyRate = selectedSpot.hourly_rate ?? 100;
      const totalCost = calculateBookingCost(hourlyRate, bookingTimeSlot);

      const booking = await createBooking({
        userId: session.userId,
        parkingId: selectedParking.id,
        spotId: selectedSpot.id,
        vehicleId: vehicles[0]?.id,
        vehiclePlate: vehicles[0]?.plate_number ?? vehicles[0]?.number_plate,
        startTime: bookingTimeSlot.startTime,
        endTime: bookingTimeSlot.endTime,
        hourlyRate,
        totalCost,
        token
      });
      setActiveBooking(booking);
      setActivePayment(null);
      setActiveTab("booking");
      setSpots((current) => current.map((spot) => (spot.id === selectedSpot.id ? { ...spot, status: 2 } : spot)));
    } catch (error) {
      handleError(error, "Бронирование не создано");
    } finally {
      setLoading(false);
    }
  }

  async function addCar(input: { numberPlate: string; brand?: string; color?: string; photos?: VehiclePhotos }) {
    if (!input.numberPlate.trim()) {
      Alert.alert("Введите номер", "Например: А123ВС124.");
      return;
    }

    setLoading(true);
    setErrorBanner(null);
    try {
      const vehicle = await addVehicle({ ...input, token });
      setVehicles((current) => [vehicle, ...current]);
    } catch (error) {
      handleError(error, "Автомобиль не добавлен");
    } finally {
      setLoading(false);
    }
  }

  async function payActiveBooking() {
    if (!activeBooking || !session) {
      return;
    }
    if (activePayment?.status === "succeeded") {
      Alert.alert("Платеж уже выполнен", "Для этого бронирования уже есть успешная mock-оплата.");
      return;
    }
    setLoading(true);
    setErrorBanner(null);
    try {
      const createdPayment = await createMockPayment({
        bookingId: activeBooking.id,
        userId: session.userId,
        amount: getBookingAmount(activeBooking),
        token
      });
      const confirmedPayment = await confirmMockPayment(createdPayment.id, token);
      const confirmedBooking = await confirmBookingAfterPayment(activeBooking.id, token);
      setActivePayment({ ...createdPayment, ...confirmedPayment, amount: confirmedPayment.amount || createdPayment.amount });
      setActiveBooking({ ...activeBooking, ...confirmedBooking, status: 2 });
      Alert.alert("Оплата выполнена", `Mock-платеж #${confirmedPayment.id} подтвержден.`);
    } catch (error) {
      handleError(error, "Оплата не прошла");
    } finally {
      setLoading(false);
    }
  }

  async function cancelActiveBooking() {
    if (!activeBooking) {
      return;
    }
    setLoading(true);
    setErrorBanner(null);
    try {
      await cancelBooking(activeBooking.id, token);
      setActiveBooking(null);
      setActivePayment(null);
      setActiveTab("parkings");
    } catch (error) {
      handleError(error, "Не удалось отменить бронь");
    } finally {
      setLoading(false);
    }
  }

  async function toggleOwnerSpot(spot: ParkingSpot) {
    const nextIsFree = spot.status !== 1;
    const nextSpot = { ...spot, status: nextIsFree ? 1 : 2, rental_enabled: nextIsFree };
    setOwnerSpots((current) => current.map((item) => (item.id === spot.id ? nextSpot : item)));
    try {
      const updated = await updateOwnerSpot({ spotId: spot.id, isFree: nextIsFree, token });
      setOwnerSpots((current) => current.map((item) => (item.id === spot.id ? updated : item)));
    } catch (error) {
      setOwnerSpots((current) => current.map((item) => (item.id === spot.id ? spot : item)));
      handleError(error, "Статус не обновлен");
    }
  }

  async function saveOwnerSpotPrice(spot: ParkingSpot, hourlyRate: number, penalty: number) {
    setLoading(true);
    setErrorBanner(null);
    try {
      const updated = await updateOwnerSpot({ spotId: spot.id, hourlyRate, penalty, token });
      setOwnerSpots((current) => current.map((item) => (item.id === spot.id ? updated : item)));
    } catch (error) {
      handleError(error, "Цена места не обновлена");
    } finally {
      setLoading(false);
    }
  }

  async function registerSpotOwnership(spotId: number, hourlyRate: number, penalty: number) {
    if (!spotId || spotId <= 0) {
      Alert.alert("Проверьте место", "Укажите ID места из карты парковки.");
      return;
    }
    setLoading(true);
    setErrorBanner(null);
    try {
      const created = await registerOwnerSpot({ spotId, hourlyRate, penalty, rentalEnabled: false, token });
      setOwnerSpots((current) => [created, ...current.filter((item) => item.id !== created.id)]);
    } catch (error) {
      handleError(error, "Место не зарегистрировано");
    } finally {
      setLoading(false);
    }
  }

  async function loadOwnerSpotReport(spot: ParkingSpot) {
    setLoading(true);
    setErrorBanner(null);
    try {
      const report = await getOwnerSpotReport(spot.id, token);
      setOwnerReports((current) => ({ ...current, [spot.id]: report }));
    } catch (error) {
      handleError(error, "Отчет по месту не загружен");
    } finally {
      setLoading(false);
    }
  }

  function handleError(error: unknown, title: string) {
    const message = getErrorMessage(error);
    if (isUnauthorizedError(error)) {
      void applySession(null);
      setErrorBanner(null);
      Alert.alert("Нужно войти заново", message);
      return;
    }
    setErrorBanner(message);
    Alert.alert(title, message);
  }

  if (sessionRestoring) {
  return (
    <SafeAreaProvider style={{ flex: 1 }}>
      <View style={styles.emptyState}>
        <ActivityIndicator color={colors.primary} />
      </View>
    </SafeAreaProvider>
  );
}

  if (!session) {
  return (
    <SafeAreaProvider style={{ flex: 1 }}>
      <AuthScreen onSession={(nextSession) => void applySession(nextSession)} />
    </SafeAreaProvider>
  );
}

  return (
    <SafeAreaProvider>
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <View style={styles.header}>
        <View>
          <Text style={styles.appName}>Зелённые парковки</Text>
          <Text style={styles.headerSubtitle}>Бронирование и аренда парковочных мест</Text>
        </View>
        {loading ? <ActivityIndicator color={colors.primary} /> : null}
      </View>

      <View style={styles.content}>
        {errorBanner ? (
          <View style={styles.errorBanner}>
            <Ionicons name="warning-outline" size={22} color={colors.danger} />
            <Text style={styles.errorBannerText}>{errorBanner}</Text>
            <Pressable onPress={loadInitialData} style={styles.errorRetry}>
              <Text style={styles.errorRetryText}>Повторить</Text>
            </Pressable>
          </View>
        ) : null}
        {activeTab === "parkings" ? (
          <ParkingScreen
            parkings={parkings}
            selectedParking={selectedParking}
            spots={spots}
            selectedSpot={selectedSpot}
            bookingTimeSlot={bookingTimeSlot}
            hasVehicles={vehicles.length > 0}
            onSelectParking={selectParking}
            onSelectSpot={setSelectedSpot}
            onBookingTimeSlotChange={setBookingTimeSlot}
            onBook={bookSelectedSpot}
          />
        ) : null}
        {activeTab === "booking" ? (
          <BookingScreen
            booking={activeBooking}
            payment={activePayment}
            parking={selectedParking}
            onPay={payActiveBooking}
            onCancel={cancelActiveBooking}
          />
        ) : null}
        {activeTab === "vehicle" ? <VehicleScreen vehicles={vehicles} onAddVehicle={addCar} /> : null}
        {activeTab === "owner" ? (
          <OwnerScreen
            availableSpots={spots}
            spots={ownerSpots}
            reports={ownerReports}
            onLoadReport={loadOwnerSpotReport}
            onRegisterSpot={registerSpotOwnership}
            onSavePrice={saveOwnerSpotPrice}
            onToggleSpot={toggleOwnerSpot}
          />
        ) : null}
        {activeTab === "profile" ? <ProfileScreen session={session} onLogout={() => void applySession(null)} /> : null}
      </View>

      <View style={styles.tabBar}>
        {tabs.map((tab) => (
          <Pressable
            key={tab.key}
            accessibilityRole="button"
            accessibilityLabel={tab.label}
            onPress={() => setActiveTab(tab.key)}
            style={[styles.tabButton, activeTab === tab.key && styles.tabButtonActive]}
          >
            <Ionicons name={tab.icon} size={20} color={activeTab === tab.key ? colors.primary : colors.muted} />
            <Text style={[styles.tabLabel, activeTab === tab.key && styles.tabLabelActive]}>{tab.label}</Text>
          </Pressable>
        ))}
      </View>
    </SafeAreaView>
    </SafeAreaProvider>
  );
}

function AuthScreen({ onSession }: { onSession: (session: AuthSession) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("tenant@example.com");
  const [password, setPassword] = useState("password123");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    try {
      const response =
        mode === "login" ? await login(email, password) : await register(email, password);
      const responseRole = String(response.user.role ?? "tenant").toLowerCase();
      onSession({
        accessToken: response.tokens.access_token,
        refreshToken: response.tokens.refresh_token,
        userId: response.user.id ?? 1,
        userName: response.user.full_name || email,
        role: responseRole.includes("landlord") ? "landlord" : "tenant",
        expiresAt: Date.now() + sessionTtlMs
      });
    } catch (error) {
      Alert.alert("Ошибка входа", getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  return (
    <View style={styles.safeArea}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.authWrap}>
        <Text style={styles.authTitle}>Зелённые парковки</Text>
        <Text style={styles.authSubtitle}>Мобильный кабинет арендатора и владельца парковочного места</Text>

        <View style={styles.segment}>
          <Pressable style={[styles.segmentButton, mode === "login" && styles.segmentActive]} onPress={() => setMode("login")}>
            <Text style={[styles.segmentText, mode === "login" && styles.segmentTextActive]}>Вход</Text>
          </Pressable>
          <Pressable style={[styles.segmentButton, mode === "register" && styles.segmentActive]} onPress={() => setMode("register")}>
            <Text style={[styles.segmentText, mode === "register" && styles.segmentTextActive]}>Регистрация</Text>
          </Pressable>
        </View>

        <View style={styles.form}>
          <TextInput
            autoCapitalize="none"
            keyboardType="email-address"
            onChangeText={setEmail}
            placeholder="Email"
            style={styles.input}
            value={email}
          />
          <TextInput
            onChangeText={setPassword}
            placeholder="Пароль"
            secureTextEntry
            style={styles.input}
            value={password}
          />
          <PrimaryButton label={mode === "login" ? "Войти" : "Создать аккаунт"} icon="log-in-outline" onPress={submit} disabled={loading} />
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

function ParkingScreen({
  parkings,
  selectedParking,
  spots,
  selectedSpot,
  bookingTimeSlot,
  hasVehicles,
  onSelectParking,
  onSelectSpot,
  onBookingTimeSlotChange,
  onBook
}: {
  parkings: Parking[];
  selectedParking: Parking | null;
  spots: ParkingSpot[];
  selectedSpot: ParkingSpot | null;
  bookingTimeSlot: BookingTimeSlot;
  hasVehicles: boolean;
  onSelectParking: (parking: Parking) => void;
  onSelectSpot: (spot: ParkingSpot | null) => void;
  onBookingTimeSlotChange: (slot: BookingTimeSlot) => void;
  onBook: () => void;
}) {
  const freeCount = spots.filter((spot) => spot.status === 1).length;
  const [calendarVisible, setCalendarVisible] = useState(false);
  const [calendarMonth, setCalendarMonth] = useState(() => new Date(bookingTimeSlot.startTime));
  const hourlyRate = selectedSpot?.hourly_rate ?? 100;
  const bookingCost = calculateBookingCost(hourlyRate, bookingTimeSlot);
  const sheetTranslateY = useRef(new Animated.Value(0)).current;
  const sheetPanResponder = useRef(
    PanResponder.create({
      onMoveShouldSetPanResponder: (_, gestureState) => Math.abs(gestureState.dy) > 8 && Math.abs(gestureState.dy) > Math.abs(gestureState.dx),
      onPanResponderMove: (_, gestureState) => {
        if (gestureState.dy > 0) {
          sheetTranslateY.setValue(gestureState.dy);
        }
      },
      onPanResponderRelease: (_, gestureState) => {
        if (gestureState.dy > 90 || gestureState.vy > 0.8) {
          Animated.timing(sheetTranslateY, {
            duration: 180,
            toValue: 420,
            useNativeDriver: true
          }).start(() => {
            sheetTranslateY.setValue(0);
            onSelectSpot(null);
          });
          return;
        }
        Animated.spring(sheetTranslateY, {
          toValue: 0,
          useNativeDriver: true
        }).start();
      }
    })
  ).current;

  useEffect(() => {
    if (selectedSpot) {
      sheetTranslateY.setValue(0);
    }
  }, [selectedSpot, sheetTranslateY]);

  return (
    <ScrollView showsVerticalScrollIndicator={false}>
      <Text style={styles.sectionTitle}>Доступные парковки</Text>
      <FlatList
        horizontal
        data={parkings}
        keyExtractor={(item) => String(item.id)}
        showsHorizontalScrollIndicator={false}
        renderItem={({ item }) => (
          <Pressable
            onPress={() => onSelectParking(item)}
            style={[styles.parkingCard, selectedParking?.id === item.id && styles.parkingCardActive]}
          >
            <Text style={styles.cardTitle}>{item.name}</Text>
            <Text style={styles.mutedText}>{item.address}</Text>
            <Text style={styles.metricText}>{item.capacity ?? item.total_spots ?? "?"} мест</Text>
          </Pressable>
        )}
      />

      <View style={styles.summaryBand}>
        <View>
          <Text style={styles.summaryValue}>{freeCount}</Text>
          <Text style={styles.summaryLabel}>свободно сейчас</Text>
        </View>
        <View>
          <Text style={styles.summaryValue}>{selectedSpot?.name ?? selectedSpot?.spot_number ?? "-"}</Text>
          <Text style={styles.summaryLabel}>выбранное место</Text>
        </View>
        <View>
          <Text style={styles.summaryValue}>{selectedSpot?.hourly_rate ?? 120} ₽</Text>
          <Text style={styles.summaryLabel}>за час</Text>
        </View>
      </View>

      <Text style={styles.sectionTitle}>Карта парковки</Text>
      {!hasVehicles ? (
        <View style={styles.notice}>
          <Ionicons name="car-outline" size={22} color={colors.primary} />
          <Text style={styles.noticeText}>Чтобы бронировать места, сначала добавьте данные автомобиля во вкладке «Авто».</Text>
        </View>
      ) : null}
      <View style={styles.mapGrid}>
        {spots.map((spot) => {
          const isFree = spot.status === 1;
          const isSelected = selectedSpot?.id === spot.id;
          return (
            <Pressable
              key={spot.id}
              disabled={!isFree || !hasVehicles}
              onPress={() => onSelectSpot(spot)}
              style={[
                styles.spot,
                (!isFree || !hasVehicles) && styles.spotBusy,
                spot.for_disabled && styles.spotSpecial,
                isSelected && styles.spotSelected
              ]}
            >
              <Text style={[styles.spotText, !isFree && styles.spotTextMuted]}>{spot.name ?? spot.spot_number}</Text>
            </Pressable>
          );
        })}
      </View>

      {false ? (
      <View style={styles.timePanel}>
        <View>
          <Text style={styles.panelKicker}>Время бронирования</Text>
          <Text style={styles.cardTitle}>{formatBookingDateTime(bookingTimeSlot.startTime)}</Text>
          <Text style={styles.mutedText}>до {formatBookingDateTime(bookingTimeSlot.endTime)}</Text>
        </View>
        <View style={styles.dateQuickRow}>
          <SecondaryButton label="Сегодня" icon="today-outline" onPress={() => onBookingTimeSlotChange(setBookingDate(bookingTimeSlot, formatDateInput(new Date())))} />
          <SecondaryButton label="+1 день" icon="chevron-forward-outline" onPress={() => onBookingTimeSlotChange(shiftBookingDay(bookingTimeSlot, 1))} />
        </View>
        <View style={styles.dateInputRow}>
          <Text style={styles.fieldLabel}>Дата</Text>
          <Pressable
            accessibilityRole="button"
            onPress={() => {
              setCalendarMonth(new Date(bookingTimeSlot.startTime));
              setCalendarVisible(true);
            }}
            style={[styles.input, styles.compactInput, styles.dateButton]}
          >
            <Ionicons name="calendar-outline" size={18} color={colors.primary} />
            <Text style={styles.dateButtonText}>{formatDateInput(bookingTimeSlot.startTime)}</Text>
          </Pressable>
        </View>
        <View style={styles.clockGrid}>
          <View style={styles.clockGroup}>
            <Text style={styles.fieldLabel}>Начало</Text>
            <View style={styles.clockInputs}>
              <TimePartInput
                max={23}
                value={bookingTimeSlot.startTime.getHours()}
                onCommit={(hour) => onBookingTimeSlotChange(setBookingClock(bookingTimeSlot, "start", String(hour), padClock(bookingTimeSlot.startTime.getMinutes())))}
              />
              <Text style={styles.clockSeparator}>:</Text>
              <TimePartInput
                max={59}
                value={bookingTimeSlot.startTime.getMinutes()}
                onCommit={(minute) => onBookingTimeSlotChange(setBookingClock(bookingTimeSlot, "start", padClock(bookingTimeSlot.startTime.getHours()), String(minute)))}
              />
            </View>
          </View>
          <View style={styles.clockGroup}>
            <Text style={styles.fieldLabel}>Окончание</Text>
            <View style={styles.clockInputs}>
              <TimePartInput
                max={23}
                value={bookingTimeSlot.endTime.getHours()}
                onCommit={(hour) => onBookingTimeSlotChange(setBookingClock(bookingTimeSlot, "end", String(hour), padClock(bookingTimeSlot.endTime.getMinutes())))}
              />
              <Text style={styles.clockSeparator}>:</Text>
              <TimePartInput
                max={59}
                value={bookingTimeSlot.endTime.getMinutes()}
                onCommit={(minute) => onBookingTimeSlotChange(setBookingClock(bookingTimeSlot, "end", padClock(bookingTimeSlot.endTime.getHours()), String(minute)))}
              />
            </View>
          </View>
        </View>
        <View style={styles.timeStepper}>
          <SecondaryButton label="-15 мин старт" icon="remove-outline" onPress={() => onBookingTimeSlotChange(shiftBookingTime(bookingTimeSlot, "start", -15))} />
          <SecondaryButton label="+15 мин конец" icon="add-outline" onPress={() => onBookingTimeSlotChange(shiftBookingTime(bookingTimeSlot, "end", 15))} />
        </View>
        <View style={styles.bookingEstimate}>
          <Text style={styles.mutedText}>Длительность: {formatBookingDuration(bookingTimeSlot)}</Text>
          <Text style={styles.mutedText}>Расчет: {hourlyRate} ₽/час = {bookingCost} ₽</Text>
        </View>
      </View>
      ) : null}
      <CalendarModal
        month={calendarMonth}
        selectedDate={bookingTimeSlot.startTime}
        visible={calendarVisible}
        onClose={() => setCalendarVisible(false)}
        onMonthChange={setCalendarMonth}
        onSelectDate={(date) => {
          onBookingTimeSlotChange(setBookingDate(bookingTimeSlot, formatDateInput(date)));
          setCalendarVisible(false);
        }}
      />


      {selectedSpot ? (
        <Modal animationType="fade" onRequestClose={() => onSelectSpot(null)} transparent visible={Boolean(selectedSpot)}>
          <Pressable style={styles.bottomSheetBackdrop} onPress={() => onSelectSpot(null)}>
            <Animated.View
              {...sheetPanResponder.panHandlers}
              style={[styles.bottomSheetPanel, styles.bookingSheetPanel, { transform: [{ translateY: sheetTranslateY }] }]}
            >
              <View style={styles.bottomSheetHandle} />
              <View style={styles.timePanel}>
                <View>
                  <Text style={styles.panelKicker}>Время бронирования</Text>
                  <Text style={styles.cardTitle}>{formatBookingDateTime(bookingTimeSlot.startTime)}</Text>
                  <Text style={styles.mutedText}>до {formatBookingDateTime(bookingTimeSlot.endTime)}</Text>
                </View>
                <View style={styles.dateQuickRow}>
                  <SecondaryButton label="Сегодня" icon="today-outline" onPress={() => onBookingTimeSlotChange(setBookingDate(bookingTimeSlot, formatDateInput(new Date())))} />
                  <SecondaryButton label="+1 день" icon="chevron-forward-outline" onPress={() => onBookingTimeSlotChange(shiftBookingDay(bookingTimeSlot, 1))} />
                </View>
                <View style={styles.dateInputRow}>
                  <Text style={styles.fieldLabel}>Дата</Text>
                  <Pressable
                    accessibilityRole="button"
                    onPress={() => {
                      setCalendarMonth(new Date(bookingTimeSlot.startTime));
                      setCalendarVisible(true);
                    }}
                    style={[styles.input, styles.compactInput, styles.dateButton]}
                  >
                    <Ionicons name="calendar-outline" size={18} color={colors.primary} />
                    <Text style={styles.dateButtonText}>{formatDateInput(bookingTimeSlot.startTime)}</Text>
                  </Pressable>
                </View>
                <View style={styles.clockGrid}>
                  <View style={styles.clockGroup}>
                    <Text style={styles.fieldLabel}>Начало</Text>
                    <View style={styles.clockInputs}>
                      <TimePartInput max={23} value={bookingTimeSlot.startTime.getHours()} onCommit={(hour) => onBookingTimeSlotChange(setBookingClock(bookingTimeSlot, "start", String(hour), padClock(bookingTimeSlot.startTime.getMinutes())))} />
                      <Text style={styles.clockSeparator}>:</Text>
                      <TimePartInput max={59} value={bookingTimeSlot.startTime.getMinutes()} onCommit={(minute) => onBookingTimeSlotChange(setBookingClock(bookingTimeSlot, "start", padClock(bookingTimeSlot.startTime.getHours()), String(minute)))} />
                    </View>
                  </View>
                  <View style={styles.clockGroup}>
                    <Text style={styles.fieldLabel}>Окончание</Text>
                    <View style={styles.clockInputs}>
                      <TimePartInput max={23} value={bookingTimeSlot.endTime.getHours()} onCommit={(hour) => onBookingTimeSlotChange(setBookingClock(bookingTimeSlot, "end", String(hour), padClock(bookingTimeSlot.endTime.getMinutes())))} />
                      <Text style={styles.clockSeparator}>:</Text>
                      <TimePartInput max={59} value={bookingTimeSlot.endTime.getMinutes()} onCommit={(minute) => onBookingTimeSlotChange(setBookingClock(bookingTimeSlot, "end", padClock(bookingTimeSlot.endTime.getHours()), String(minute)))} />
                    </View>
                  </View>
                </View>
                <View style={styles.bookingEstimate}>
                  <Text style={styles.mutedText}>Место {selectedSpot.name ?? selectedSpot.spot_number} · {formatBookingDuration(bookingTimeSlot)}</Text>
                  <Text style={styles.mutedText}>Расчет: {hourlyRate} ₽/час = {bookingCost} ₽</Text>
                </View>
                <PrimaryButton label="Забронировать" icon="calendar-outline" onPress={onBook} />
              </View>
            </Animated.View>
          </Pressable>
        </Modal>
      ) : null}
    </ScrollView>
  );
}

function BookingScreen({
  booking,
  payment,
  parking,
  onPay,
  onCancel
}: {
  booking: Booking | null;
  payment: Payment | null;
  parking: Parking | null;
  onPay: () => void;
  onCancel: () => void;
}) {
  if (!booking) {
    return (
      <EmptyState
        icon="time-outline"
        title="Активной брони нет"
        text="Выберите свободное место на карте парковки и создайте бронирование."
      />
    );
  }

  return (
    <ScrollView showsVerticalScrollIndicator={false}>
      <View style={styles.detailPanel}>
        <Text style={styles.panelKicker}>Активное бронирование</Text>
        <Text style={styles.detailTitle}>Место {booking.spot_name ?? booking.parking_spot_id ?? booking.parking_spot}</Text>
        <Text style={styles.mutedText}>{parking?.name ?? `Парковка #${booking.parking_id}`}</Text>
        <View style={[styles.bookingStatus, booking.status === 2 ? styles.bookingStatusConfirmed : styles.bookingStatusPending]}>
          <Ionicons
            name={booking.status === 2 ? "checkmark-circle-outline" : "hourglass-outline"}
            size={18}
            color={booking.status === 2 ? colors.success : colors.warning}
          />
          <Text style={[styles.bookingStatusText, booking.status === 2 ? styles.bookingStatusTextConfirmed : styles.bookingStatusTextPending]}>
            {getBookingStatusText(booking.status)}
          </Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Начало</Text>
          <Text style={styles.detailValue}>{formatTime(booking.start_time)}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Окончание</Text>
          <Text style={styles.detailValue}>{formatTime(booking.end_time)}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Стоимость</Text>
          <Text style={styles.detailValue}>{getBookingAmount(booking)} ₽</Text>
        </View>
      </View>

      <View style={styles.routePanel}>
        <Ionicons name="navigate-outline" size={24} color={colors.primary} />
        <View style={styles.routeText}>
          <Text style={styles.cardTitle}>Маршрут до места</Text>
          <Text style={styles.mutedText}>В базовой версии показан ориентир на цифровой карте. Подключение навигации зависит от CV-маршрутизации.</Text>
        </View>
      </View>

      <View style={styles.paymentPanel}>
        <View style={styles.paymentHeader}>
          <View>
            <Text style={styles.panelKicker}>Оплата</Text>
            <Text style={styles.cardTitle}>Mock-платеж без банка</Text>
          </View>
          <View style={[styles.paymentBadge, payment?.status === "succeeded" ? styles.paymentBadgePaid : styles.paymentBadgePending]}>
            <Text style={[styles.paymentBadgeText, payment?.status === "succeeded" ? styles.paymentBadgeTextPaid : styles.paymentBadgeTextPending]}>
              {payment?.status === "succeeded" ? "Оплачено" : "К оплате"}
            </Text>
          </View>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Сумма</Text>
          <Text style={styles.detailValue}>{payment?.amount || getBookingAmount(booking)} ₽</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Способ</Text>
          <Text style={styles.detailValue}>Mock provider</Text>
        </View>
        {payment?.status === "succeeded" ? (
          <View style={styles.confirmedNotice}>
            <Ionicons name="receipt-outline" size={20} color={colors.success} />
            <Text style={styles.confirmedNoticeText}>Чек #{payment.id}: платеж {payment.provider_payment_id ?? "mock"} успешно подтвержден.</Text>
          </View>
        ) : (
          <PrimaryButton label="Оплатить без банка" icon="card-outline" onPress={onPay} />
        )}
      </View>
      <SecondaryButton label="Отменить бронь" icon="close-circle-outline" onPress={onCancel} />
    </ScrollView>
  );
}

function VehicleScreen({
  vehicles,
  onAddVehicle
}: {
  vehicles: Vehicle[];
  onAddVehicle: (input: { numberPlate: string; brand?: string; color?: string; photos?: VehiclePhotos }) => void;
}) {
  const [plate, setPlate] = useState("");
  const [brand, setBrand] = useState("");
  const [color, setColor] = useState("");
  const [frontPhoto, setFrontPhoto] = useState("");
  const [backPhoto, setBackPhoto] = useState("");
  const [leftPhoto, setLeftPhoto] = useState("");
  const [rightPhoto, setRightPhoto] = useState("");

  const photoSetters: Record<keyof VehiclePhotos, (value: string) => void> = {
    front: setFrontPhoto,
    back: setBackPhoto,
    left: setLeftPhoto,
    right: setRightPhoto
  };

  async function selectPhoto(side: keyof VehiclePhotos, source: "camera" | "library") {
    const permission =
      source === "camera"
        ? await ImagePicker.requestCameraPermissionsAsync()
        : await ImagePicker.requestMediaLibraryPermissionsAsync();
    if (!permission.granted) {
      Alert.alert("Нет доступа", source === "camera" ? "Разрешите доступ к камере." : "Разрешите доступ к галерее.");
      return;
    }

    const result =
      source === "camera"
        ? await ImagePicker.launchCameraAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.8 })
        : await ImagePicker.launchImageLibraryAsync({ mediaTypes: ImagePicker.MediaTypeOptions.Images, quality: 0.8 });

    if (!result.canceled && result.assets[0]?.uri) {
      photoSetters[side](result.assets[0].uri);
    }
  }

  const photos: VehiclePhotos = {
    front: frontPhoto,
    back: backPhoto,
    left: leftPhoto,
    right: rightPhoto
  };

  return (
    <ScrollView showsVerticalScrollIndicator={false}>
      <Text style={styles.sectionTitle}>Мои автомобили</Text>
      {vehicles.map((vehicle) => (
        <View key={vehicle.id} style={styles.listItem}>
          <Ionicons name="car-sport-outline" size={24} color={colors.primary} />
          <View style={styles.listText}>
            <Text style={styles.cardTitle}>{vehicle.number_plate ?? vehicle.plate_number}</Text>
            <Text style={styles.mutedText}>{vehicle.name ?? "Автомобиль пользователя"}</Text>
          </View>
        </View>
      ))}

      <View style={styles.formBlock}>
        <Text style={styles.sectionTitle}>Добавить автомобиль</Text>
        <TextInput autoCapitalize="characters" onChangeText={setPlate} placeholder="А123ВС124" style={styles.input} value={plate} />
        <TextInput onChangeText={setBrand} placeholder="Марка авто" style={styles.input} value={brand} />
        <TextInput onChangeText={setColor} placeholder="Цвет авто" style={styles.input} value={color} />
        <View style={styles.photoGrid}>
          {([
            ["front", "Спереди"],
            ["back", "Сзади"],
            ["left", "Слева"],
            ["right", "Справа"]
          ] as Array<[keyof VehiclePhotos, string]>).map(([side, label]) => (
            <View key={side} style={styles.photoSlot}>
              {photos[side] ? <Image source={{ uri: photos[side] }} style={styles.photoPreview} /> : <Ionicons name="image-outline" size={30} color={colors.muted} />}
              <Text style={styles.fieldLabel}>{label}</Text>
              <View style={styles.photoActions}>
                <Pressable style={styles.iconButton} onPress={() => selectPhoto(side, "library")}>
                  <Ionicons name="images-outline" size={18} color={colors.primary} />
                </Pressable>
                <Pressable style={styles.iconButton} onPress={() => selectPhoto(side, "camera")}>
                  <Ionicons name="camera-outline" size={18} color={colors.primary} />
                </Pressable>
              </View>
            </View>
          ))}
        </View>
        <PrimaryButton
          label="Сохранить автомобиль"
          icon="add-circle-outline"
          onPress={() => {
            onAddVehicle({
              numberPlate: plate,
              brand,
              color,
              photos: {
                front: frontPhoto,
                back: backPhoto,
                left: leftPhoto,
                right: rightPhoto
              }
            });
            setPlate("");
            setBrand("");
            setColor("");
            setFrontPhoto("");
            setBackPhoto("");
            setLeftPhoto("");
            setRightPhoto("");
          }}
        />
      </View>
    </ScrollView>
  );
}

function OwnerScreen({
  availableSpots,
  spots,
  reports,
  onLoadReport,
  onRegisterSpot,
  onSavePrice,
  onToggleSpot
}: {
  availableSpots: ParkingSpot[];
  spots: ParkingSpot[];
  reports: Record<number, OwnerSpotReport>;
  onLoadReport: (spot: ParkingSpot) => void;
  onRegisterSpot: (spotId: number, hourlyRate: number, penalty: number) => void;
  onSavePrice: (spot: ParkingSpot, hourlyRate: number, penalty: number) => void;
  onToggleSpot: (spot: ParkingSpot) => void;
}) {
  const [spotIdDraft, setSpotIdDraft] = useState("");
  const [priceDraft, setPriceDraft] = useState("120");
  const [penaltyDraft, setPenaltyDraft] = useState("500");
  const [ownershipMapVisible, setOwnershipMapVisible] = useState(false);
  const [selectedOwnershipSpot, setSelectedOwnershipSpot] = useState<ParkingSpot | null>(null);
  const income = useMemo(
    () => Object.values(reports).reduce((sum, report) => sum + report.transfer_amount, 0),
    [reports]
  );

  return (
    <ScrollView showsVerticalScrollIndicator={false}>
      <Text style={styles.sectionTitle}>Выставить свое место</Text>
      <View style={styles.notice}>
        <Ionicons name="key-outline" size={22} color={colors.primary} />
        <Text style={styles.noticeText}>Откройте место, которое находится в вашей собственности, чтобы оно стало доступно для бронирования. Закрытое место не показывается как доступное.</Text>
      </View>

      <View style={styles.summaryBand}>
        <View>
          <Text style={styles.summaryValue}>{spots.length}</Text>
          <Text style={styles.summaryLabel}>мест под управлением</Text>
        </View>
        <View>
          <Text style={styles.summaryValue}>{income} ₽</Text>
          <Text style={styles.summaryLabel}>доход за период</Text>
        </View>
      </View>

      <Text style={styles.sectionTitle}>Управление местами</Text>
      <View style={styles.formBlock}>
        <Text style={styles.sectionTitle}>Зарегистрировать место</Text>
        <SecondaryButton label={selectedOwnershipSpot ? `Место ${selectedOwnershipSpot.name ?? selectedOwnershipSpot.spot_number}` : "Добавить собственное место"} icon="map-outline" onPress={() => setOwnershipMapVisible(true)} />
        <TextInput keyboardType="number-pad" onChangeText={setPriceDraft} placeholder="Цена за час" style={styles.input} value={priceDraft} />
        <TextInput keyboardType="number-pad" onChangeText={setPenaltyDraft} placeholder="Штраф" style={styles.input} value={penaltyDraft} />
        <PrimaryButton
          label="Закрепить за мной"
          icon="key-outline"
          onPress={() => onRegisterSpot(selectedOwnershipSpot?.id ?? Number(spotIdDraft), Number(priceDraft) || 0, Number(penaltyDraft) || 0)}
        />
      </View>

      <Modal animationType="slide" onRequestClose={() => setOwnershipMapVisible(false)} transparent visible={ownershipMapVisible}>
        <Pressable style={styles.bottomSheetBackdrop} onPress={() => setOwnershipMapVisible(false)}>
          <Pressable style={styles.ownerMapPanel}>
            <View style={styles.bottomSheetHandle} />
            <Text style={styles.sectionTitle}>Выберите место на карте</Text>
            <View style={styles.mapGrid}>
              {availableSpots.map((spot) => {
                const isOwned = spots.some((ownerSpot) => ownerSpot.id === spot.id);
                const isSelected = selectedOwnershipSpot?.id === spot.id;
                return (
                  <Pressable
                    key={`owner-map-${spot.id}`}
                    disabled={isOwned}
                    onPress={() => {
                      setSelectedOwnershipSpot(spot);
                      setSpotIdDraft(String(spot.id));
                      setOwnershipMapVisible(false);
                    }}
                    style={[
                      styles.spot,
                      isOwned && styles.spotBusy,
                      isSelected && styles.spotSelected,
                      spot.for_disabled && styles.spotSpecial
                    ]}
                  >
                    <Text style={[styles.spotText, isOwned && styles.spotTextMuted]}>{spot.name ?? spot.spot_number}</Text>
                  </Pressable>
                );
              })}
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      {spots.map((spot) => (
        <View key={spot.id} style={styles.ownerRow}>
          <View>
            <Text style={styles.cardTitle}>Место {spot.name ?? spot.spot_number}</Text>
            <Text style={styles.mutedText}>{spot.hourly_rate ?? 120} ₽/час · штраф 500 ₽</Text>
          </View>
          <Pressable
            accessibilityRole="switch"
            accessibilityState={{ checked: spot.status === 1 }}
            onPress={() => onToggleSpot(spot)}
            style={[styles.statusPill, spot.status === 1 ? styles.statusFree : styles.statusBusy]}
          >
            <Text style={styles.statusPillText}>{spot.status === 1 ? "Открыто" : "Закрыто"}</Text>
          </Pressable>
        </View>
      ))}
      {spots.length ? (
        <View style={styles.formBlock}>
          <Text style={styles.sectionTitle}>Отчетность</Text>
          {spots.map((spot) => (
            <View key={`report-${spot.id}`} style={styles.detailPanel}>
              <Text style={styles.cardTitle}>Место {spot.name ?? spot.spot_number}</Text>
              <Text style={styles.mutedText}>
                {reports[spot.id] ? `${reports[spot.id].transfer_count} переводов · ${reports[spot.id].transfer_amount} ₽` : "Отчет еще не загружен"}
              </Text>
              <SecondaryButton label="Загрузить отчет" icon="document-text-outline" onPress={() => onLoadReport(spot)} />
              <SecondaryButton
                label="Сохранить цену"
                icon="save-outline"
                onPress={() => onSavePrice(spot, Number(priceDraft) || (spot.hourly_rate ?? 120), Number(penaltyDraft) || (spot.penalty ?? 500))}
              />
            </View>
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}

function ProfileScreen({ session, onLogout }: { session: AuthSession; onLogout: () => void }) {
  return (
    <ScrollView showsVerticalScrollIndicator={false}>
      <View style={styles.detailPanel}>
        <Text style={styles.panelKicker}>Профиль</Text>
        <Text style={styles.detailTitle}>{session.userName}</Text>
        <Text style={styles.mutedText}>{session.role === "landlord" ? "Арендодатель" : "Арендатор"}</Text>
      </View>
      <View style={styles.notice}>
        <Ionicons name="notifications-outline" size={22} color={colors.primary} />
        <Text style={styles.noticeText}>Push-уведомления о статусе брони, нарушениях и штрафах заложены в сценарии НТО и вынесены в следующий этап интеграции.</Text>
      </View>
      <View style={styles.notice}>
        <Ionicons name="server-outline" size={22} color={colors.primary} />
        <Text style={styles.noticeText}>API: {getApiBaseUrl()}</Text>
      </View>
      <SecondaryButton label="Выйти" icon="log-out-outline" onPress={onLogout} />
    </ScrollView>
  );
}

function EmptyState({ icon, title, text }: { icon: keyof typeof Ionicons.glyphMap; title: string; text: string }) {
  return (
    <View style={styles.emptyState}>
      <Ionicons name={icon} size={42} color={colors.primary} />
      <Text style={styles.emptyTitle}>{title}</Text>
      <Text style={styles.emptyText}>{text}</Text>
    </View>
  );
}

function PrimaryButton({
  label,
  icon,
  onPress,
  disabled
}: {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
  disabled?: boolean;
}) {
  return (
    <Pressable onPress={onPress} disabled={disabled} style={[styles.primaryButton, disabled && styles.disabledButton]}>
      <Ionicons name={icon} size={20} color="#FFFFFF" />
      <Text style={styles.primaryButtonText}>{label}</Text>
    </Pressable>
  );
}

function SecondaryButton({
  label,
  icon,
  onPress
}: {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  onPress: () => void;
}) {
  return (
    <Pressable onPress={onPress} style={styles.secondaryButton}>
      <Ionicons name={icon} size={20} color={colors.primary} />
      <Text style={styles.secondaryButtonText}>{label}</Text>
    </Pressable>
  );
}

function TimePartInput({ value, max, onCommit }: { value: number; max: number; onCommit: (value: number) => void }) {
  const [draft, setDraft] = useState(() => padClock(value));

  useEffect(() => {
    setDraft(padClock(value));
  }, [value]);

  function commit() {
    if (!draft.trim()) {
      setDraft(padClock(value));
      return;
    }
    const parsed = Number(draft);
    if (!Number.isInteger(parsed)) {
      setDraft(padClock(value));
      return;
    }
    const clamped = Math.min(max, Math.max(0, parsed));
    setDraft(padClock(clamped));
    onCommit(clamped);
  }

  return (
    <TextInput
      keyboardType="number-pad"
      maxLength={2}
      onBlur={commit}
      onChangeText={(text) => setDraft(text.replace(/\D/g, "").slice(0, 2))}
      onSubmitEditing={commit}
      selectTextOnFocus
      style={[styles.input, styles.compactInput, styles.clockInput]}
      value={draft}
    />
  );
}

function CalendarModal({
  visible,
  month,
  selectedDate,
  onClose,
  onMonthChange,
  onSelectDate
}: {
  visible: boolean;
  month: Date;
  selectedDate: Date;
  onClose: () => void;
  onMonthChange: (month: Date) => void;
  onSelectDate: (date: Date) => void;
}) {
  const days = getCalendarDays(month);
  const monthTitle = new Intl.DateTimeFormat("ru-RU", { month: "long", year: "numeric" }).format(month);

  return (
    <Modal animationType="fade" onRequestClose={onClose} transparent visible={visible}>
      <Pressable style={styles.modalBackdrop} onPress={onClose}>
        <Pressable style={styles.calendarPanel}>
          <View style={styles.calendarHeader}>
            <Pressable accessibilityRole="button" onPress={() => onMonthChange(addCalendarMonths(month, -1))} style={styles.iconButton}>
              <Ionicons name="chevron-back-outline" size={22} color={colors.primary} />
            </Pressable>
            <Text style={styles.calendarTitle}>{monthTitle}</Text>
            <Pressable accessibilityRole="button" onPress={() => onMonthChange(addCalendarMonths(month, 1))} style={styles.iconButton}>
              <Ionicons name="chevron-forward-outline" size={22} color={colors.primary} />
            </Pressable>
          </View>
          <View style={styles.weekRow}>
            {["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"].map((day) => (
              <Text key={day} style={styles.weekdayText}>{day}</Text>
            ))}
          </View>
          <View style={styles.calendarGrid}>
            {days.map((day, index) => {
              const isSelected = day && formatDateInput(day) === formatDateInput(selectedDate);
              return (
                <Pressable
                  key={day ? formatDateInput(day) : `blank-${index}`}
                  disabled={!day}
                  onPress={() => day && onSelectDate(day)}
                  style={[styles.calendarDay, isSelected && styles.calendarDaySelected, !day && styles.calendarDayBlank]}
                >
                  <Text style={[styles.calendarDayText, isSelected && styles.calendarDayTextSelected]}>{day ? day.getDate() : ""}</Text>
                </Pressable>
              );
            })}
          </View>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function formatAvailability(spot: ParkingSpot) {
  if (!spot.availability_start_time && !spot.availability_end_time) {
    return "Сейчас";
  }
  const start = spot.availability_start_time ? formatTime(spot.availability_start_time) : "сейчас";
  const end = spot.availability_end_time ? formatTime(spot.availability_end_time) : "без ограничения";
  return `${start} - ${end}`;
}

function padClock(value: number) {
  return value.toString().padStart(2, "0");
}

function addCalendarMonths(value: Date, months: number) {
  return new Date(value.getFullYear(), value.getMonth() + months, 1);
}

function getCalendarDays(month: Date) {
  const firstDay = new Date(month.getFullYear(), month.getMonth(), 1);
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const mondayBasedOffset = (firstDay.getDay() + 6) % 7;
  const days: Array<Date | null> = Array.from({ length: mondayBasedOffset }, () => null);
  for (let day = 1; day <= daysInMonth; day += 1) {
    days.push(new Date(month.getFullYear(), month.getMonth(), day));
  }
  while (days.length % 7 !== 0) {
    days.push(null);
  }
  return days;
}

function getBookingAmount(booking: Booking) {
  if (booking.total_cost && booking.total_cost > 0) {
    return Math.round(booking.total_cost);
  }
  const start = new Date(booking.start_time).getTime();
  const end = new Date(booking.end_time).getTime();
  const minutes = Number.isFinite(start) && Number.isFinite(end) ? Math.max(0, Math.ceil((end - start) / 60_000)) : 0;
  return Math.round(((booking.hourly_rate ?? 100) * minutes) / 60);
}

function getBookingStatusText(status: number) {
  if (status === 1) {
    return "Ожидает подтверждения";
  }
  if (status === 2) {
    return "Подтверждена";
  }
  if (status === 3) {
    return "Завершена";
  }
  if (status === 4) {
    return "Отменена";
  }
  if (status === 5) {
    return "Истекла";
  }
  return "Статус неизвестен";
}

const styles = StyleSheet.create({
  safeArea: {
    flex: 1,
    backgroundColor: colors.background
  },
  authWrap: {
    flex: 1,
    justifyContent: "center",
    padding: spacing.xl
  },
  authTitle: {
    color: colors.text,
    fontSize: 34,
    fontWeight: "800",
    marginBottom: spacing.sm
  },
  authSubtitle: {
    color: colors.muted,
    fontSize: 16,
    lineHeight: 22,
    marginBottom: spacing.xl
  },
  form: {
    gap: spacing.md
  },
  header: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingVertical: spacing.md
  },
  appName: {
    color: colors.text,
    fontSize: 22,
    fontWeight: "800"
  },
  headerSubtitle: {
    color: colors.muted,
    fontSize: 12,
    marginTop: 2
  },
  content: {
    flex: 1,
    paddingHorizontal: spacing.lg
  },
  errorBanner: {
    alignItems: "center",
    backgroundColor: "#FFF1F0",
    borderColor: "#FDA29B",
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.md,
    padding: spacing.md
  },
  errorBannerText: {
    color: colors.text,
    flex: 1,
    fontSize: 12,
    lineHeight: 17
  },
  errorRetry: {
    borderColor: colors.danger,
    borderRadius: 6,
    borderWidth: 1,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs
  },
  errorRetryText: {
    color: colors.danger,
    fontSize: 12,
    fontWeight: "800"
  },
  tabBar: {
    backgroundColor: colors.surface,
    borderTopColor: colors.border,
    borderTopWidth: 1,
    flexDirection: "row",
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.sm
  },
  tabButton: {
    alignItems: "center",
    borderRadius: 8,
    flex: 1,
    gap: 2,
    minHeight: 52,
    justifyContent: "center"
  },
  tabButtonActive: {
    backgroundColor: colors.surfaceAlt
  },
  tabLabel: {
    color: colors.muted,
    fontSize: 11,
    fontWeight: "700"
  },
  tabLabelActive: {
    color: colors.primary
  },
  segment: {
    backgroundColor: colors.surfaceAlt,
    borderRadius: 8,
    flexDirection: "row",
    padding: 4
  },
  segmentButton: {
    alignItems: "center",
    borderRadius: 6,
    flex: 1,
    paddingVertical: spacing.md
  },
  segmentActive: {
    backgroundColor: colors.surface
  },
  segmentText: {
    color: colors.muted,
    fontWeight: "700"
  },
  segmentTextActive: {
    color: colors.text
  },
  input: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    color: colors.text,
    fontSize: 16,
    minHeight: 50,
    paddingHorizontal: spacing.md
  },
  compactInput: {
    minHeight: 42,
    paddingHorizontal: spacing.sm
  },
  fieldLabel: {
    color: colors.muted,
    fontSize: 12,
    fontWeight: "800",
    marginBottom: spacing.xs
  },
  sectionTitle: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "800",
    marginBottom: spacing.md,
    marginTop: spacing.md
  },
  parkingCard: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    marginRight: spacing.md,
    minHeight: 132,
    padding: spacing.md,
    width: 230
  },
  parkingCardActive: {
    borderColor: colors.primary,
    borderWidth: 2
  },
  cardTitle: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "800"
  },
  mutedText: {
    color: colors.muted,
    fontSize: 13,
    lineHeight: 18,
    marginTop: spacing.xs
  },
  metricText: {
    color: colors.primary,
    fontSize: 20,
    fontWeight: "800",
    marginTop: "auto"
  },
  summaryBand: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: spacing.lg,
    padding: spacing.lg
  },
  summaryValue: {
    color: colors.text,
    fontSize: 22,
    fontWeight: "900"
  },
  summaryLabel: {
    color: colors.muted,
    fontSize: 11,
    marginTop: 2,
    maxWidth: 90
  },
  mapGrid: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    padding: spacing.md
  },
  spot: {
    alignItems: "center",
    aspectRatio: 1.25,
    backgroundColor: "#E5F4EE",
    borderColor: colors.success,
    borderRadius: 6,
    borderWidth: 1,
    justifyContent: "center",
    width: "22%"
  },
  spotBusy: {
    backgroundColor: "#F1F5F9",
    borderColor: colors.border
  },
  spotSpecial: {
    backgroundColor: "#E7F0FF",
    borderColor: colors.primary
  },
  spotSelected: {
    backgroundColor: colors.primary,
    borderColor: colors.primaryDark,
    borderWidth: 2
  },
  spotText: {
    color: colors.text,
    fontSize: 13,
    fontWeight: "800"
  },
  spotTextMuted: {
    color: colors.muted
  },
  timePanel: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: spacing.md,
    marginTop: spacing.md,
    padding: spacing.lg
  },
  dateQuickRow: {
    flexDirection: "row",
    gap: spacing.sm
  },
  dateInputRow: {
    gap: spacing.xs
  },
  dateInput: {
    width: "100%"
  },
  dateButton: {
    alignItems: "center",
    flexDirection: "row",
    gap: spacing.sm
  },
  dateButtonText: {
    color: colors.text,
    fontSize: 15,
    fontWeight: "800"
  },
  clockGrid: {
    flexDirection: "row",
    gap: spacing.md
  },
  clockGroup: {
    flex: 1
  },
  clockInputs: {
    alignItems: "center",
    flexDirection: "row",
    gap: spacing.xs
  },
  clockInput: {
    flex: 1,
    minWidth: 54,
    textAlign: "center"
  },
  clockSeparator: {
    color: colors.text,
    fontSize: 18,
    fontWeight: "800"
  },
  timeStepper: {
    flexDirection: "row",
    gap: spacing.sm
  },
  bookingEstimate: {
    borderTopColor: colors.border,
    borderTopWidth: 1,
    paddingTop: spacing.sm
  },
  modalBackdrop: {
    alignItems: "center",
    backgroundColor: "rgba(15, 23, 42, 0.36)",
    flex: 1,
    justifyContent: "center",
    padding: spacing.lg
  },
  bottomSheetBackdrop: {
    backgroundColor: "rgba(15, 23, 42, 0.36)",
    flex: 1,
    justifyContent: "flex-end"
  },
  bottomSheetPanel: {
    backgroundColor: colors.background,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    maxHeight: "86%",
    padding: spacing.lg
  },
  bookingSheetPanel: {
    marginBottom: 74
  },
  ownerMapPanel: {
    backgroundColor: colors.background,
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    maxHeight: "78%",
    padding: spacing.lg
  },
  bottomSheetHandle: {
    alignSelf: "center",
    backgroundColor: colors.border,
    borderRadius: 2,
    height: 4,
    marginBottom: spacing.md,
    width: 46
  },
  calendarPanel: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    maxWidth: 360,
    padding: spacing.lg,
    width: "100%"
  },
  calendarHeader: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: spacing.md
  },
  calendarTitle: {
    color: colors.text,
    fontSize: 16,
    fontWeight: "900",
    textTransform: "capitalize"
  },
  iconButton: {
    alignItems: "center",
    borderColor: colors.border,
    borderRadius: 6,
    borderWidth: 1,
    height: 40,
    justifyContent: "center",
    width: 40
  },
  weekRow: {
    flexDirection: "row",
    marginBottom: spacing.xs
  },
  weekdayText: {
    color: colors.muted,
    flex: 1,
    fontSize: 12,
    fontWeight: "800",
    textAlign: "center"
  },
  calendarGrid: {
    flexDirection: "row",
    flexWrap: "wrap"
  },
  calendarDay: {
    alignItems: "center",
    aspectRatio: 1,
    borderRadius: 6,
    justifyContent: "center",
    width: "14.2857%"
  },
  calendarDayBlank: {
    opacity: 0
  },
  calendarDaySelected: {
    backgroundColor: colors.primary
  },
  calendarDayText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "800"
  },
  calendarDayTextSelected: {
    color: "#FFFFFF"
  },
  durationRow: {
    flexDirection: "row",
    gap: spacing.sm
  },
  durationButton: {
    alignItems: "center",
    backgroundColor: colors.surfaceAlt,
    borderColor: colors.border,
    borderRadius: 6,
    borderWidth: 1,
    flex: 1,
    minHeight: 42,
    justifyContent: "center"
  },
  durationButtonActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary
  },
  durationText: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "800"
  },
  durationTextActive: {
    color: "#FFFFFF"
  },
  spotInfoPanel: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    marginTop: spacing.md,
    padding: spacing.lg
  },
  detailPanel: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    padding: spacing.lg
  },
  panelKicker: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "800",
    textTransform: "uppercase"
  },
  detailTitle: {
    color: colors.text,
    fontSize: 28,
    fontWeight: "900",
    marginTop: spacing.xs
  },
  bookingStatus: {
    alignItems: "center",
    alignSelf: "flex-start",
    borderRadius: 6,
    flexDirection: "row",
    gap: spacing.xs,
    marginTop: spacing.md,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs
  },
  bookingStatusConfirmed: {
    backgroundColor: "#E5F4EE"
  },
  bookingStatusPending: {
    backgroundColor: "#FFF7E6"
  },
  bookingStatusText: {
    fontSize: 13,
    fontWeight: "800"
  },
  bookingStatusTextConfirmed: {
    color: colors.success
  },
  bookingStatusTextPending: {
    color: colors.warning
  },
  detailRow: {
    borderTopColor: colors.border,
    borderTopWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: spacing.md,
    paddingTop: spacing.md
  },
  detailRowCompact: {
    borderTopColor: colors.border,
    borderTopWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm
  },
  detailLabel: {
    color: colors.muted,
    fontSize: 14
  },
  detailValue: {
    color: colors.text,
    fontSize: 14,
    fontWeight: "800"
  },
  routePanel: {
    alignItems: "flex-start",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.md,
    padding: spacing.lg
  },
  routeText: {
    flex: 1
  },
  paymentPanel: {
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    marginTop: spacing.md,
    padding: spacing.lg
  },
  paymentHeader: {
    alignItems: "center",
    flexDirection: "row",
    justifyContent: "space-between"
  },
  paymentBadge: {
    borderRadius: 6,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs
  },
  paymentBadgePaid: {
    backgroundColor: "#E5F4EE"
  },
  paymentBadgePending: {
    backgroundColor: "#FFF7E6"
  },
  paymentBadgeText: {
    fontSize: 12,
    fontWeight: "800"
  },
  paymentBadgeTextPaid: {
    color: colors.success
  },
  paymentBadgeTextPending: {
    color: colors.warning
  },
  confirmedNotice: {
    alignItems: "center",
    backgroundColor: "#E5F4EE",
    borderColor: "#B7E4CE",
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    gap: spacing.sm,
    marginTop: spacing.lg,
    padding: spacing.md
  },
  confirmedNoticeText: {
    color: colors.text,
    flex: 1,
    fontSize: 13,
    lineHeight: 18
  },
  listItem: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    gap: spacing.md,
    marginBottom: spacing.md,
    padding: spacing.lg
  },
  listText: {
    flex: 1
  },
  photoGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm
  },
  photoSlot: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    gap: spacing.xs,
    padding: spacing.sm,
    width: "48%"
  },
  photoPreview: {
    aspectRatio: 1.4,
    borderRadius: 6,
    width: "100%"
  },
  photoActions: {
    flexDirection: "row",
    gap: spacing.sm
  },
  formBlock: {
    marginTop: spacing.lg
  },
  ownerRow: {
    alignItems: "center",
    backgroundColor: colors.surface,
    borderColor: colors.border,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: spacing.md,
    padding: spacing.lg
  },
  statusPill: {
    alignItems: "center",
    borderRadius: 6,
    minWidth: 82,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm
  },
  statusFree: {
    backgroundColor: colors.success
  },
  statusBusy: {
    backgroundColor: colors.reserved
  },
  statusPillText: {
    color: "#FFFFFF",
    fontSize: 12,
    fontWeight: "800"
  },
  notice: {
    alignItems: "flex-start",
    backgroundColor: "#E7F0FF",
    borderColor: "#BFD7FF",
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.md,
    padding: spacing.md
  },
  noticeText: {
    color: colors.text,
    flex: 1,
    fontSize: 13,
    lineHeight: 18
  },
  emptyState: {
    alignItems: "center",
    flex: 1,
    justifyContent: "center",
    padding: spacing.xl
  },
  emptyTitle: {
    color: colors.text,
    fontSize: 22,
    fontWeight: "900",
    marginTop: spacing.md,
    textAlign: "center"
  },
  emptyText: {
    color: colors.muted,
    fontSize: 15,
    lineHeight: 21,
    marginTop: spacing.sm,
    textAlign: "center"
  },
  primaryButton: {
    alignItems: "center",
    backgroundColor: colors.primary,
    borderRadius: 8,
    flexDirection: "row",
    gap: spacing.sm,
    justifyContent: "center",
    marginTop: spacing.lg,
    minHeight: 52,
    paddingHorizontal: spacing.lg
  },
  primaryButtonText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontWeight: "800"
  },
  disabledButton: {
    opacity: 0.45
  },
  secondaryButton: {
    alignItems: "center",
    borderColor: colors.primary,
    borderRadius: 8,
    borderWidth: 1,
    flexDirection: "row",
    gap: spacing.sm,
    justifyContent: "center",
    marginTop: spacing.md,
    minHeight: 50,
    paddingHorizontal: spacing.lg
  },
  secondaryButtonText: {
    color: colors.primary,
    fontSize: 16,
    fontWeight: "800"
  }
});

