import AsyncStorage from "@react-native-async-storage/async-storage";
import { AuthSession } from "../../types";

const sessionStorageKey = "parking.mobile.auth.session";
export const sessionTtlMs = 24 * 60 * 60 * 1000;

export async function loadStoredSession(): Promise<AuthSession | null> {
  const rawSession = await AsyncStorage.getItem(sessionStorageKey);
  if (!rawSession) {
    return null;
  }

  try {
    const session = JSON.parse(rawSession) as AuthSession;
    if (!session.accessToken || !session.refreshToken || typeof session.expiresAt !== "number" || session.expiresAt <= Date.now()) {
      await clearStoredSession();
      return null;
    }
    return session;
  } catch {
    await clearStoredSession();
    return null;
  }
}

export async function saveStoredSession(session: AuthSession) {
  await AsyncStorage.setItem(sessionStorageKey, JSON.stringify(session));
}

export async function clearStoredSession() {
  await AsyncStorage.removeItem(sessionStorageKey);
}
