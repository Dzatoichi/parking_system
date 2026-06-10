function wsProtocol() {
  return window.location.protocol === "https:" ? "wss:" : "ws:";
}

function isViteDevServer() {
  return window.location.port === "3000";
}

function normalizePath(path: string) {
  return path.startsWith("/") ? path : `/${path}`;
}

export function parkingWsUrl(path: string) {
  const configured = import.meta.env.VITE_API_WS_URL as string | undefined;
  if (configured) return `${configured.replace(/\/$/, "")}${normalizePath(path)}`;

  if (isViteDevServer()) {
    return `${wsProtocol()}//${window.location.hostname}:8000${normalizePath(path)}`;
  }

  return `${wsProtocol()}//${window.location.host}/api${normalizePath(path)}`;
}

export function cvWsUrl(path: string) {
  const configured = import.meta.env.VITE_CV_WS_URL as string | undefined;
  if (configured) return `${configured.replace(/\/$/, "")}${normalizePath(path)}`;

  if (isViteDevServer()) {
    return `${wsProtocol()}//${window.location.hostname}:8001${normalizePath(path)}`;
  }

  return `${wsProtocol()}//${window.location.host}/cv${normalizePath(path)}`;
}
