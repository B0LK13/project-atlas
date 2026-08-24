import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface ChangedDelta {
  added?: string[];
  removed?: string[];
  modified?: string[];
  added_count?: number;
  removed_count?: number;
  modified_count?: number;
  truncated?: boolean;
}

export interface ChangedSemantic {
  meaningful?: boolean;
  signals?: string[];
}

export interface ChangedLens {
  project_id?: string;
  title?: string;
  summary?: string | null;
  value?: string | null;
  status?: string;
  rollup?: string;
  delta?: ChangedDelta;
  semantic?: ChangedSemantic;
  notes?: string[];
  source_drift?: {
    status?: string;
    reason?: string;
    reason_code?: string;
    changed_paths?: string[];
  };
  honesty?: Record<string, boolean | string>;
  truth_boundary?: string;
  authority?: string;
}

export function useLiveChanged(projectId: string | null) {
  const [changed, setChanged] = useState<ChangedLens | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setChanged(null);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    if (!projectId) {
      setChanged(null);
      setDataSource(null);
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    liveApiFetch(`/v1/changed?project=${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`changed HTTP ${response.status}`);
        }
        return (await response.json()) as ChangedLens;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setChanged(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setChanged(null);
        setDataSource(null);
        setError(exc instanceof Error ? exc.message : "changed unavailable");
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

  return { changed, error, loading, dataSource };
}
