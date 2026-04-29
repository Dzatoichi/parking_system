export function getApiErrorMessage(error: unknown, fallback: string) {
  if (!error) {
    return null;
  }

  if (typeof error === "object" && error !== null) {
    const maybeResponse = error as {
      response?: { data?: { detail?: string } };
      message?: string;
    };

    return maybeResponse.response?.data?.detail ?? maybeResponse.message ?? fallback;
  }

  return fallback;
}
