import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** LIVE_API facade snapshot. Not a backup bundle. Facade ≠ authority. */

export interface SnapshotView {
  package_id?: string;
  projects?: Array<Record<string, unknown>>;
  knowledge?: Array<Record<string, unknown>>;
  graph?: {
    available?: boolean;
    node_count?: number;
    edge_count?: number;
    authority?: string;
  };
  health?: Record<string, unknown>;
  [key: string]: unknown;
}

export function useLiveSnapshot(): {
  snapshot: SnapshotView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [snapshot, setSnapshot] = useState<SnapshotView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const resp = await liveApiFetch("/v1/snapshot");
          if (resp.ok) {
            const body = (await resp.json()) as SnapshotView;
            if (!cancelled) {
              setSnapshot(body);
              setDataSource("live_api");
              setError(null);
            }
            return;
          }
          if (!cancelled) {
            setError(`snapshot HTTP ${resp.status}`);
            setSnapshot(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "snapshot load failed");
            setSnapshot(null);
            setDataSource(null);
          }
          return;
        }
      }
      if (!cancelled) {
        setSnapshot(null);
        setDataSource("demo_stub");
        setError(null);
      }
    }

    load()
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "snapshot load failed");
          setSnapshot(null);
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

  return { snapshot, error, loading, dataSource };
}
