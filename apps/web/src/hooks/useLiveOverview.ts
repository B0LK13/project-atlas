import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface OverviewLens {
  project_id?: string;
  status?: string;
  title?: string;
  summary?: string | null;
  value?: string | null;
  coverage?: Record<string, string>;
  notes?: string[];
  honesty?: Record<string, boolean | string>;
  truth_boundary?: string;
  authority?: string;
}

export function useLiveOverview(projectId: string | null) {
  const [overview, setOverview] = useState<OverviewLens | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setOverview(null);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    if (!projectId) {
      setOverview(null);
      setDataSource(null);
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    liveApiFetch(`/v1/overview?project=${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`overview HTTP ${response.status}`);
        }
        return (await response.json()) as OverviewLens;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setOverview(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setOverview(null);
        setDataSource(null);
        setError(exc instanceof Error ? exc.message : "overview unavailable");
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

  return { overview, error, loading, dataSource };
}
