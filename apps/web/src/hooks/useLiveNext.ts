import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface NextQueueItem {
  kind?: string;
  title?: string;
  why?: string;
  action?: string;
  evidence?: string[];
  source_package?: string;
  rank?: number;
}

export interface NextLens {
  project_id?: string;
  summary?: string | null;
  status?: string;
  value?: string | null;
  primary?: NextQueueItem;
  queue?: NextQueueItem[];
  blockers?: NextQueueItem[];
  unknowns?: NextQueueItem[];
  why_cannot_advance?: string | null;
  suggested_next_work?: string[];
  honesty?: Record<string, boolean | string>;
  truth_boundary?: string;
  authority?: string;
}

export function useLiveNext(projectId: string | null) {
  const [next, setNext] = useState<NextLens | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setNext(null);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    if (!projectId) {
      setNext(null);
      setDataSource(null);
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    liveApiFetch(`/v1/next?project=${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`next HTTP ${response.status}`);
        }
        return (await response.json()) as NextLens;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setNext(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setNext(null);
        setDataSource(null);
        setError(exc instanceof Error ? exc.message : "next unavailable");
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

  return { next, error, loading, dataSource };
}
