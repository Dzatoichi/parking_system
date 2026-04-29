import { Analytics } from "../components/Analytics";
import { CameraNetwork } from "../components/cameras-network/CameraNetwork";
import { Dashboard } from "../components/Dashboard";
import { ParkingMap } from "../components/ParkingMap";
import { ParkingMarker } from "../components/parking-marker/ParkingMarker";
import { Settings } from "../components/Settings";
import { VehicleSearch } from "../components/VehicleSearch";

export type Screen =
  | "dashboard"
  | "parking-map"
  | "vehicle-search"
  | "analytics"
  | "cameras-network"
  | "parking-marker"
  | "settings";

export const DEFAULT_SCREEN: Screen = "dashboard";

const fullscreenScreens = new Set<Screen>(["cameras-network", "parking-marker"]);

export function isFullscreenScreen(screen: Screen) {
  return fullscreenScreens.has(screen);
}

type RenderScreenParams = {
  currentScreen: Screen;
  onNavigate: (screen: Screen) => void;
};

export function renderScreen({ currentScreen, onNavigate }: RenderScreenParams) {
  switch (currentScreen) {
    case "dashboard":
      return <Dashboard onNavigate={onNavigate} />;
    case "parking-map":
      return <ParkingMap />;
    case "vehicle-search":
      return <VehicleSearch />;
    case "analytics":
      return <Analytics />;
    case "cameras-network":
      return <CameraNetwork />;
    case "parking-marker":
      return <ParkingMarker />;
    case "settings":
      return <Settings />;
    default:
      return <Dashboard onNavigate={onNavigate} />;
  }
}
