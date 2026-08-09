import { useEffect, useState } from "react";
import type { ReadStatus } from "../types";

const STUB_URL = "/sample-read-status.json";

export function useReadStatus(): {
  status: ReadStatus | null;
  error: string | null;
  loading: boolean;
} {
  const [status, setStatus] = useState<ReadStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    fetch(STUB_URL)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`stub HTTP ${response.status}`);
        }
        return (await response.json()) as ReadStatus;
      })
      .then((payload) => {
        if (!cancelled) {
          setStatus(payload);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "stub load failed");
          setStatus(null);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { status, error, loading };
}
