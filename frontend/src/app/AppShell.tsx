import type { ReactNode } from "react";

import { Header } from "../components/Header";
import { Sidebar } from "../components/Sidebar";
import type { Screen } from "./screens";

type AppShellProps = {
  children: ReactNode;
  currentScreen: Screen;
  isFullscreen: boolean;
  onScreenChange: (screen: Screen) => void;
};

export function AppShell({
  children,
  currentScreen,
  isFullscreen,
  onScreenChange,
}: AppShellProps) {
  return (
    <div
      className="h-screen w-full flex flex-col bg-gray-50"
      style={{ fontFamily: "Inter, sans-serif" }}
    >
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar currentScreen={currentScreen} onScreenChange={onScreenChange} />
        <main
          className={`flex-1 overflow-auto transition-all duration-300 ease-in-out ${
            isFullscreen ? "" : "p-6"
          }`}
        >
          {children}
        </main>
      </div>
    </div>
  );
}
