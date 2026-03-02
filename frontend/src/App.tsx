import React, { useState } from "react";
import { Header } from "./components/Header";
import { Sidebar } from "./components/Sidebar";
import { Dashboard } from "./components/Dashboard";
import { ParkingMap } from "./components/ParkingMap";
import { VehicleSearch } from "./components/VehicleSearch";
import { Analytics } from "./components/Analytics";
import { Settings } from "./components/Settings";

export type Screen =
  | "dashboard"
  | "parking-map"
  | "vehicle-search"
  | "analytics"
  | "settings";

export default function App() {
  const [currentScreen, setCurrentScreen] =
    useState<Screen>("dashboard");

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
      case "settings":
        return <Settings />;
      default:
        return <Dashboard />;
    }
  };

  return (
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
        <main className="flex-1 overflow-auto p-6 transition-all duration-300 ease-in-out">
          {renderScreen()}
        </main>
      </div>
    </div>
  );
}