import { useEffect, useState } from "react";
import type { DataSource, ReadStatus } from "../types";

/** AS-2.1-WEB-LIVE-001 deepen: LIVE_API first; demo stub isolated + labelled. */
const STUB_URL = "/sample-read-status.json";

function envFlag(name: string): string | undefined {
  const env = (import.meta as ImportMeta & { env?: Record<string, string> }).env;
  return env?.[name];
}

function apiBase(): string {
  return (envFlag("VITE_ATLAS_API_BASE") ?? "http://127.0.0.1:8765").replace(/\/$/, "");
}

function demoOnly(): boolean {
  const raw = (envFlag("VITE_ATLAS_DEMO_ONLY") ?? "").trim().toLowerCase();
  return raw === "1" || raw === "true" || raw === "yes";
}

function stampDemo(status: ReadStatus): ReadStatus {
  return {
    ...status,
    read_plane: "stub",
    data_source: "demo_stub",
    demo_isolated: true,
    ui_canonical: false,
    graph_authority: false,
    unknown_equals_healthy: false,
  };
}

function stampLive(status: ReadStatus): ReadStatus {
  return {
    ...status,
    data_source: "live_api",
    demo_isolated: false,
    ui_canonical: false,
    graph_authority: false,
    unknown_equals_healthy: false,
  };
}

async function loadLiveOrStub(): Promise<{ status: ReadStatus; source: DataSource }> {
  if (!demoOnly()) {
    const liveUrl = `${apiBase()}/v1/snapshot`;
    try {
      const live = await fetch(liveUrl);
      if (live.ok) {
        const snap = (await live.json()) as {
          health?: { read_status?: ReadStatus };
        };
        const status = snap.health?.read_status;
        if (status && typeof status === "object") {
          return { status: stampLive(status), source: "live_api" };
        }
      }
    } catch {
      // fall through to isolated demo stub
    }
  }
  const response = await fetch(STUB_URL);
  if (!response.ok) {
    throw new Error(`demo stub HTTP ${response.status}`);
  }
  const stub = (await response.json()) as ReadStatus;
  return { status: stampDemo(stub), source: "demo_stub" };
}

export function useReadStatus(): {
  status: ReadStatus | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
  livePreferred: boolean;
} {
  const [status, setStatus] = useState<ReadStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);
  const livePreferred = !demoOnly();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loadLiveOrStub()
      .then(({ status: payload, source }) => {
        if (!cancelled) {
          setStatus(payload);
          setDataSource(source);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "status load failed");
          setStatus(null);
          setDataSource(null);
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

  return { status, error, loading, dataSource, livePreferred };
}
