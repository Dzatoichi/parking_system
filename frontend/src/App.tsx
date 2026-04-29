import { useState } from "react";

import { AppShell } from "./app/AppShell";
import {
  DEFAULT_SCREEN,
  isFullscreenScreen,
  renderScreen,
  type Screen,
} from "./app/screens";

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<Screen>(DEFAULT_SCREEN);

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
