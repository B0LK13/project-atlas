import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface SessionCaptureRow {
  capture_id?: string;
  project_id?: string;
  kind?: string;
  source?: string;
  summary?: string;
  authority?: boolean;
  path?: string;
  status?: string;
}

export interface SessionCaptureInventory {
  package_id?: string;
  project_id?: string | null;
  capture_count?: number;
  captures?: SessionCaptureRow[];
  available?: boolean;
  honesty?: Record<string, boolean | string>;
}

export function useLiveSessionCaptures(projectId: string | null) {
  const [inventory, setInventory] = useState<SessionCaptureInventory | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setInventory(null);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    const path = projectId
      ? `/v1/session-captures?project=${encodeURIComponent(projectId)}`
      : "/v1/session-captures";
    setLoading(true);
    liveApiFetch(path)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`session-captures HTTP ${response.status}`);
        }
        return (await response.json()) as SessionCaptureInventory;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setInventory(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setInventory(null);
        setDataSource(null);
        setError(
          exc instanceof Error ? exc.message : "session captures unavailable",
        );
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  return { inventory, error, loading, dataSource };
}
