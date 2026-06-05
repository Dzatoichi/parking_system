declare namespace NodeJS {
  interface ProcessEnv {
    EXPO_PUBLIC_DEMO_MODE?: string;
    EXPO_PUBLIC_API_URL?: string;
    EXPO_PUBLIC_API_PORT?: string;
    EXPO_PUBLIC_PARKING_API_URL?: string;
    EXPO_PUBLIC_AUTH_API_URL?: string;
  }
}

declare const process: {
  env: NodeJS.ProcessEnv;
};
