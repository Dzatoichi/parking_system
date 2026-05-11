import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { authAPI, userAPI, type User } from '../services/authApi';

interface AuthState {
  user: User | null;
  accessToken: string | null;
  isLoading: boolean;
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  getValidToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

const REFRESH_KEY = "refresh_token";

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    user: null,
    accessToken: null,
    isLoading: true,
  });
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function scheduleRefresh(delayMs = 14 * 60 * 1000) {
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    refreshTimerRef.current = setTimeout(silentRefresh, delayMs);
  }

  async function silentRefresh() {
    const rt = localStorage.getItem(REFRESH_KEY);
    if (!rt) return logout();
    try {
      const { data: tokens } = await authAPI.refresh(rt);
      localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
      setState((prev) => ({ ...prev, accessToken: tokens.access_token }));
      scheduleRefresh();
    } catch {
      logout();
    }
  }

  useEffect(() => {
    const rt = localStorage.getItem(REFRESH_KEY);
    if (!rt) {
      setState((prev) => ({ ...prev, isLoading: false }));
      return;
    }
    authAPI.refresh(rt)
      .then(async ({ data: tokens }) => {
        localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
        const { data: user } = await userAPI.getMe(tokens.access_token);
        setState({ user, accessToken: tokens.access_token, isLoading: false });
        scheduleRefresh();
      })
      .catch(() => {
        localStorage.removeItem(REFRESH_KEY);
        setState({ user: null, accessToken: null, isLoading: false });
      });
  }, []);

  async function login(email: string, password: string) {
    const { data } = await authAPI.login(email, password);
    localStorage.setItem(REFRESH_KEY, data.tokens.refresh_token);
    setState({ user: data.user, accessToken: data.tokens.access_token, isLoading: false });
    scheduleRefresh();
  }

  async function logout() {
    const rt = localStorage.getItem(REFRESH_KEY);
    if (rt) await authAPI.logout(rt).catch(() => {});
    localStorage.removeItem(REFRESH_KEY);
    if (refreshTimerRef.current) clearTimeout(refreshTimerRef.current);
    setState({ user: null, accessToken: null, isLoading: false });
  }

  async function getValidToken(): Promise<string | null> {
    if (state.accessToken) return state.accessToken;
    const rt = localStorage.getItem(REFRESH_KEY);
    if (!rt) return null;
    try {
      const { data: tokens } = await authAPI.refresh(rt);
      localStorage.setItem(REFRESH_KEY, tokens.refresh_token);
      setState((prev) => ({ ...prev, accessToken: tokens.access_token }));
      scheduleRefresh();
      return tokens.access_token;
    } catch {
      return null;
    }
  }

  return (
    <AuthContext.Provider value={{ ...state, login, logout, getValidToken }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}