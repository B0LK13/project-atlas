import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface DecisionItem {
  title?: string;
  source?: string;
  kind?: string;
  status?: string;
  authority?: string;
}

export interface DecisionsLens {
  project_id?: string;
  status?: string;
  title?: string;
  summary?: string | null;
  decisions?: DecisionItem[];
  decision_count?: number;
  active_governing_count?: number;
  honesty?: Record<string, boolean | string>;
  truth_boundary?: string;
  authority?: string;
}

export function useLiveDecisions(projectId: string | null) {
  const [decisions, setDecisions] = useState<DecisionsLens | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setDecisions(null);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    if (!projectId) {
      setDecisions(null);
      setDataSource(null);
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    liveApiFetch(`/v1/decisions?project=${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`decisions HTTP ${response.status}`);
        }
        return (await response.json()) as DecisionsLens;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setDecisions(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setDecisions(null);
        setDataSource(null);
        setError(exc instanceof Error ? exc.message : "decisions unavailable");
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

  return { decisions, error, loading, dataSource };
}
