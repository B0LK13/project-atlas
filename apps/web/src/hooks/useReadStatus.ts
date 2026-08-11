import { useEffect, useState } from "react";
import {
  LiveApiAuthError,
  liveApiDemoOnly,
  liveApiFetch,
} from "../api/liveApi";
import type { DataSource, ReadStatus } from "../types";

/** AS-2.1-WEB-LIVE-001 deepen: LIVE_API first; demo stub isolated + labelled. */
const STUB_URL = "/sample-read-status.json";

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

interface LoadResult {
  status: ReadStatus;
  source: DataSource;
  /**
   * Set only when LIVE_API was preferred but could not be reached/parsed, so
   * the demo stub shown below is a *fallback*, not a chosen demo. Keeps the
   * "no silent stub fallback labelled LIVE" invariant honest for the UI.
   */
  liveError: string | null;
}

async function loadLiveOrStub(): Promise<LoadResult> {
  let liveError: string | null = null;
  if (!liveApiDemoOnly()) {
    try {
      const live = await liveApiFetch("/v1/snapshot");
      if (live.ok) {
        const snap = (await live.json()) as {
          health?: { read_status?: ReadStatus };
        };
        const status = snap.health?.read_status;
        if (status && typeof status === "object") {
          return { status: stampLive(status), source: "live_api", liveError: null };
        }
        liveError = "LIVE_API snapshot missing read_status";
      } else {
        liveError = `LIVE_API HTTP ${live.status}`;
      }
    } catch (err: unknown) {
      if (err instanceof LiveApiAuthError) {
        // Missing per-launch Bearer is not a silent stub fallback — fail closed.
        throw err;
      }
      // Unreachable / CORS-blocked LIVE_API: fall back to isolated demo stub,
      // but remember *why* so the UI can label it as a fallback (not chosen).
      liveError = err instanceof Error ? err.message : "LIVE_API unreachable";
    }
  }
  const response = await fetch(STUB_URL);
  if (!response.ok) {
    throw new Error(`demo stub HTTP ${response.status}`);
  }
  const stub = (await response.json()) as ReadStatus;
  return { status: stampDemo(stub), source: "demo_stub", liveError };
}

export function useReadStatus(): {
  status: ReadStatus | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
  livePreferred: boolean;
  /** Reason LIVE_API was unreachable when a demo *fallback* is shown, else null. */
  liveError: string | null;
} {
  const [status, setStatus] = useState<ReadStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);
  const [liveError, setLiveError] = useState<string | null>(null);
  const livePreferred = !liveApiDemoOnly();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loadLiveOrStub()
      .then(({ status: payload, source, liveError: reason }) => {
        if (!cancelled) {
          setStatus(payload);
          setDataSource(source);
          setLiveError(reason);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "status load failed");
          setStatus(null);
          setDataSource(null);
          setLiveError(null);
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

  return { status, error, loading, dataSource, livePreferred, liveError };
}
