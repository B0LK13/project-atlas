import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** LIVE_API session-capture list; demo fallback is honest unknown (no invent). */

export interface SessionCaptureRow {
  capture_id?: string;
  project_id?: string;
  kind?: string;
  source?: string;
  summary?: string;
  path?: string;
  decisions?: string[];
  changes?: string[];
  next_work?: string[];
  unknowns?: string[];
}

export interface CaptureListView {
  package_id?: string;
  capture_count: number;
  captures: SessionCaptureRow[];
  project_id?: string | null;
  honesty?: {
    lens_is_authority?: boolean;
    unknown_is_valid?: boolean;
    capture_is_layer_b?: boolean;
    authentic_pilot?: boolean;
  };
  available: boolean;
  data_source?: DataSource;
  demo_isolated?: boolean;
}

const EMPTY_UNKNOWN: CaptureListView = {
  capture_count: 0,
  captures: [],
  available: false,
  data_source: "demo_stub",
  demo_isolated: true,
  honesty: {
    lens_is_authority: false,
    unknown_is_valid: true,
    capture_is_layer_b: false,
    authentic_pilot: false,
  },
};

export function useLiveCaptures(projectId: string | null): {
  inventory: CaptureListView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [inventory, setInventory] = useState<CaptureListView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const qs = projectId
            ? `?project=${encodeURIComponent(projectId)}`
            : "";
          const resp = await liveApiFetch(`/v1/captures${qs}`);
          if (resp.ok) {
            const body = (await resp.json()) as CaptureListView;
            if (!cancelled) {
              setInventory({
                ...body,
                available: true,
                data_source: "live_api",
                demo_isolated: false,
              });
              setDataSource("live_api");
              setError(null);
            }
            return;
          }
          if (!cancelled) {
            setError(`captures HTTP ${resp.status}`);
            setInventory(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "captures load failed");
            setInventory(null);
            setDataSource(null);
          }
          return;
        }
      }
      if (!cancelled) {
        setInventory(EMPTY_UNKNOWN);
        setDataSource("demo_stub");
        setError(null);
      }
    }

    load()
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "captures load failed");
          setInventory(null);
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
  }, [projectId]);

  return { inventory, error, loading, dataSource };
}
