import React, { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { Dashboard } from "./components/Dashboard";
import { ParkingMap } from "./components/ParkingMap";
import { VehicleSearch } from "./components/VehicleSearch";
import { Analytics } from "./components/Analytics";
import { Settings } from "./components/Settings";
import { CameraNetwork } from "./components/cameras-network/CameraNetwork";
import { ParkingMarker } from "./components/parking-marker/ParkingMarker";

export type Screen =
  | "dashboard"
  | "parking-map"
  | "vehicle-search"
  | "analytics"
  | "cameras-network"
  | "parking-marker"
  | "settings";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30000,
    },
  },
});

export default function App() {
  const [currentScreen, setCurrentScreen] = useState<Screen>("dashboard");

  const renderScreen = () => {
    switch (currentScreen) {
      case "dashboard":
        return <Dashboard />;
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
        return <Dashboard />;
    }
  };

  const isFullscreen = currentScreen === "cameras-network" || currentScreen === "parking-marker";

  return (
    <QueryClientProvider client={queryClient}>
      <div
        className="h-screen w-full flex flex-col bg-gray-50"
        style={{ fontFamily: "Inter, sans-serif" }}
      >
        <Header />
        <div className="flex flex-1 overflow-hidden">
          <Sidebar
            currentScreen={currentScreen}
            onScreenChange={setCurrentScreen}
          />
          <main className={`flex-1 overflow-auto transition-all duration-300 ease-in-out ${isFullscreen ? "" : "p-6"}`}>
            {renderScreen()}
          </main>
        </div>
      </div>
    </QueryClientProvider>
  );
}
