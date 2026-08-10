import { useEffect, useState } from "react";
import type { ReadStatus } from "../types";

/** AS-2.1-WEB-LIVE-001: prefer LIVE_API, fall back to sample stub. */
const STUB_URL = "/sample-read-status.json";

function apiBase(): string {
  const env = (import.meta as ImportMeta & { env?: Record<string, string> }).env;
  return (env?.VITE_ATLAS_API_BASE ?? "http://127.0.0.1:8765").replace(/\/$/, "");
}

async function loadLiveOrStub(): Promise<ReadStatus> {
  const liveUrl = `${apiBase()}/v1/snapshot`;
  try {
    const live = await fetch(liveUrl);
    if (live.ok) {
      const snap = (await live.json()) as {
        health?: { read_status?: ReadStatus };
      };
      const status = snap.health?.read_status;
      if (status && typeof status === "object") {
        return status;
      }
    }
  } catch {
    // fall through to stub
  }
  const response = await fetch(STUB_URL);
  if (!response.ok) {
    throw new Error(`stub HTTP ${response.status}`);
  }
  return (await response.json()) as ReadStatus;
}

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
    loadLiveOrStub()
      .then((payload) => {
        if (!cancelled) {
          setStatus(payload);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "status load failed");
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
