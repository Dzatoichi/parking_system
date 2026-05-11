import { useState } from "react";
import { useAuth } from "./app/AuthContext";
import { Login } from "./components/Login";

import { AppShell } from "./app/AppShell";
import {
  DEFAULT_SCREEN,
  isFullscreenScreen,
  renderScreen,
  type Screen,
} from "./app/screens";

export default function App() {
  const { user, isLoading } = useAuth();
  const [currentScreen, setCurrentScreen] = useState<Screen>(DEFAULT_SCREEN);

  if (isLoading) return <div className="h-screen flex items-center justify-center">Загрузка…</div>;
  if (!user) return <Login />;  // ← весь незалогиненный трафик сюда

  return (
    <AppShell
      currentScreen={currentScreen}
      isFullscreen={isFullscreenScreen(currentScreen)}
      onScreenChange={setCurrentScreen}
    >
      {renderScreen({ currentScreen, onNavigate: setCurrentScreen })}
    </AppShell>
  );
}
