import { Ionicons } from "@expo/vector-icons";
import { StatusBar } from "expo-status-bar";
import { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  FlatList,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  SafeAreaView,
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
  getSpots,
  getVehicles,
  isUnauthorizedError,
  login,
  register,
  updateOwnerSpot
} from "./src/api";
import { colors, spacing } from "./src/theme";
import { AuthSession, Booking, Parking, ParkingSpot, Payment, UserRole, Vehicle } from "./src/types";

type TabKey = "parkings" | "booking" | "vehicle" | "owner" | "profile";

const tabs: Array<{ key: TabKey; label: string; icon: keyof typeof Ionicons.glyphMap }> = [
  { key: "parkings", label: "Парковки", icon: "map-outline" },
  { key: "booking", label: "Бронь", icon: "time-outline" },
  { key: "vehicle", label: "Авто", icon: "car-outline" },
  { key: "owner", label: "Места", icon: "business-outline" },
  { key: "profile", label: "Профиль", icon: "person-outline" }
];

export default function App() {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("parkings");
  const [parkings, setParkings] = useState<Parking[]>([]);
  const [spots, setSpots] = useState<ParkingSpot[]>([]);
  const [vehicles, setVehicles] = useState<Vehicle[]>([]);
  const [selectedParking, setSelectedParking] = useState<Parking | null>(null);
  const [selectedSpot, setSelectedSpot] = useState<ParkingSpot | null>(null);
  const [activeBooking, setActiveBooking] = useState<Booking | null>(null);
  const [activePayment, setActivePayment] = useState<Payment | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorBanner, setErrorBanner] = useState<string | null>(null);

  const token = session?.accessToken;

  useEffect(() => {
    if (!session) {
      return;
    }

    void loadInitialData();
  }, [session]);

  async function loadInitialData() {
    setLoading(true);
    setErrorBanner(null);
    try {
      const [parkingList, vehicleList, currentBooking] = await Promise.all([
        getParkings(token),
        getVehicles(token),
        getActiveBooking(token)
      ]);
      setParkings(parkingList);
      setVehicles(vehicleList);
      setActiveBooking(currentBooking);
      setActivePayment(null);
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
    if (!selectedParking || !selectedSpot) {
      Alert.alert("Выберите место", "Сначала выберите парковку и свободное парковочное место.");
      return;
    }

    setLoading(true);
    setErrorBanner(null);
    try {
      const booking = await createBooking({
        parkingId: selectedParking.id,
        spotId: selectedSpot.id,
        vehicleId: vehicles[0]?.id,
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

  async function addCar(numberPlate: string) {
    if (!numberPlate.trim()) {
      Alert.alert("Введите номер", "Например: А123ВС124.");
      return;
    }

    setLoading(true);
    setErrorBanner(null);
    try {
      const vehicle = await addVehicle(numberPlate, token);
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
    setSpots((current) => current.map((item) => (item.id === spot.id ? { ...item, status: nextIsFree ? 1 : 2 } : item)));
    try {
      await updateOwnerSpot(spot.id, nextIsFree, token);
    } catch (error) {
      setSpots((current) => current.map((item) => (item.id === spot.id ? spot : item)));
      handleError(error, "Статус не обновлен");
    }
  }

  function handleError(error: unknown, title: string) {
    const message = getErrorMessage(error);
    if (isUnauthorizedError(error)) {
      setSession(null);
      setErrorBanner(null);
      Alert.alert("Нужно войти заново", message);
      return;
    }
    setErrorBanner(message);
    Alert.alert(title, message);
  }

  if (!session) {
    return <AuthScreen onSession={setSession} />;
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <View style={styles.header}>
        <View>
          <Text style={styles.appName}>Smart Parking</Text>
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
            onSelectParking={selectParking}
            onSelectSpot={setSelectedSpot}
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
          <OwnerScreen role={session.role} spots={spots} onToggleSpot={toggleOwnerSpot} />
        ) : null}
        {activeTab === "profile" ? <ProfileScreen session={session} onLogout={() => setSession(null)} /> : null}
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
  );
}

function AuthScreen({ onSession }: { onSession: (session: AuthSession) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("tenant@example.com");
  const [password, setPassword] = useState("password123");
  const [role, setRole] = useState<UserRole>("tenant");
  const [loading, setLoading] = useState(false);

  async function submit() {
    setLoading(true);
    try {
      const response =
        mode === "login" ? await login(email, password) : await register(email, password, role);
      const responseRole = String(response.user.role ?? role).toLowerCase();
      onSession({
        accessToken: response.tokens.access_token,
        refreshToken: response.tokens.refresh_token,
        userId: response.user.id ?? 1,
        userName: response.user.full_name || email,
        role: responseRole.includes("landlord") ? "landlord" : role
      });
    } catch (error) {
      Alert.alert("Ошибка входа", getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  return (
    <SafeAreaView style={styles.safeArea}>
      <StatusBar style="dark" />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.authWrap}>
        <Text style={styles.authTitle}>Smart Parking</Text>
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
          {mode === "register" ? (
            <View style={styles.segment}>
              <Pressable style={[styles.segmentButton, role === "tenant" && styles.segmentActive]} onPress={() => setRole("tenant")}>
                <Text style={[styles.segmentText, role === "tenant" && styles.segmentTextActive]}>Арендатор</Text>
              </Pressable>
              <Pressable style={[styles.segmentButton, role === "landlord" && styles.segmentActive]} onPress={() => setRole("landlord")}>
                <Text style={[styles.segmentText, role === "landlord" && styles.segmentTextActive]}>Владелец</Text>
              </Pressable>
            </View>
          ) : null}
          <PrimaryButton label={mode === "login" ? "Войти" : "Создать аккаунт"} icon="log-in-outline" onPress={submit} disabled={loading} />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

function ParkingScreen({
  parkings,
  selectedParking,
  spots,
  selectedSpot,
  onSelectParking,
  onSelectSpot,
  onBook
}: {
  parkings: Parking[];
  selectedParking: Parking | null;
  spots: ParkingSpot[];
  selectedSpot: ParkingSpot | null;
  onSelectParking: (parking: Parking) => void;
  onSelectSpot: (spot: ParkingSpot) => void;
  onBook: () => void;
}) {
  const freeCount = spots.filter((spot) => spot.status === 1).length;

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
      <View style={styles.mapGrid}>
        {spots.map((spot) => {
          const isFree = spot.status === 1;
          const isSelected = selectedSpot?.id === spot.id;
          return (
            <Pressable
              key={spot.id}
              disabled={!isFree}
              onPress={() => onSelectSpot(spot)}
              style={[
                styles.spot,
                !isFree && styles.spotBusy,
                spot.for_disabled && styles.spotSpecial,
                isSelected && styles.spotSelected
              ]}
            >
              <Text style={[styles.spotText, !isFree && styles.spotTextMuted]}>{spot.name ?? spot.spot_number}</Text>
            </Pressable>
          );
        })}
      </View>

      <PrimaryButton label="Забронировать выбранное место" icon="calendar-outline" onPress={onBook} disabled={!selectedSpot} />
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

function VehicleScreen({ vehicles, onAddVehicle }: { vehicles: Vehicle[]; onAddVehicle: (plate: string) => void }) {
  const [plate, setPlate] = useState("");

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
        <PrimaryButton
          label="Сохранить автомобиль"
          icon="add-circle-outline"
          onPress={() => {
            onAddVehicle(plate);
            setPlate("");
          }}
        />
      </View>
    </ScrollView>
  );
}

function OwnerScreen({
  role,
  spots,
  onToggleSpot
}: {
  role: UserRole;
  spots: ParkingSpot[];
  onToggleSpot: (spot: ParkingSpot) => void;
}) {
  const income = useMemo(() => spots.filter((spot) => spot.status !== 1).length * 240, [spots]);

  return (
    <ScrollView showsVerticalScrollIndicator={false}>
      {role !== "landlord" ? (
        <View style={styles.notice}>
          <Ionicons name="information-circle-outline" size={22} color={colors.primary} />
          <Text style={styles.noticeText}>Экран показывает базовый сценарий арендодателя из НТО. Для полной модели прав нужна backend-роль landlord.</Text>
        </View>
      ) : null}

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
      {spots.slice(0, 8).map((spot) => (
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

function formatTime(value: string) {
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(value));
}

function getBookingAmount(booking: Booking) {
  if (booking.total_cost && booking.total_cost > 0) {
    return Math.round(booking.total_cost);
  }
  const start = new Date(booking.start_time).getTime();
  const end = new Date(booking.end_time).getTime();
  const hours = Number.isFinite(start) && Number.isFinite(end) ? Math.max(1, Math.ceil((end - start) / 3_600_000)) : 2;
  return Math.round((booking.hourly_rate ?? 100) * hours);
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
