import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface StateSignals {
  pending_reviews?: number;
  unresolved_conflicts?: number;
  stale_claims?: number;
  sources_complete?: number;
  sources_failed?: number;
  verified_claims?: number;
}

export interface StateLens {
  project_id?: string;
  status?: string;
  title?: string;
  summary?: string | null;
  lifecycle?: string;
  rollup?: string;
  signals?: StateSignals;
  honesty?: Record<string, boolean | string>;
  truth_boundary?: string;
  authority?: string;
}

export function useLiveState(projectId: string | null) {
  const [state, setState] = useState<StateLens | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setState(null);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    if (!projectId) {
      setState(null);
      setDataSource(null);
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    liveApiFetch(`/v1/state?project=${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`state HTTP ${response.status}`);
        }
        return (await response.json()) as StateLens;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setState(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setState(null);
        setDataSource(null);
        setError(exc instanceof Error ? exc.message : "state unavailable");
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

  return { state, error, loading, dataSource };
}
