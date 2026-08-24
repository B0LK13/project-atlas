import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface UnknownSignals {
  pending_reviews?: number;
  unresolved_conflicts?: number;
  stale_claims?: number;
  claims_withheld?: number;
  sources_failed?: number;
  lifecycle?: string;
  coverage_absent?: boolean | number;
  unknown_items?: string[];
}

export interface UnknownLens {
  project_id?: string;
  title?: string;
  summary?: string | null;
  value?: string | null;
  status?: string;
  rollup?: string;
  signals?: UnknownSignals;
  notes?: string[];
  honesty?: Record<string, boolean | string>;
  truth_boundary?: string;
  authority?: string;
}

export function useLiveUnknown(projectId: string | null) {
  const [unknown, setUnknown] = useState<UnknownLens | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setUnknown(null);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    if (!projectId) {
      setUnknown(null);
      setDataSource(null);
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    liveApiFetch(`/v1/unknown?project=${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`unknown HTTP ${response.status}`);
        }
        return (await response.json()) as UnknownLens;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setUnknown(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setUnknown(null);
        setDataSource(null);
        setError(exc instanceof Error ? exc.message : "unknown unavailable");
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

  return { unknown, error, loading, dataSource };
}
