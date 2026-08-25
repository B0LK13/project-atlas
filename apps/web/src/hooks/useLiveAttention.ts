import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface AttentionItem {
  level?: string;
  kind?: string;
  reason_code?: string;
  why_seeing_this?: string;
  why_it_matters?: string;
  what_to_do?: string;
  subject_id?: string | null;
}

export interface AttentionLens {
  project_id?: string;
  rollup?: string;
  item_count?: number;
  care_about?: AttentionItem[];
  items?: AttentionItem[];
  honesty?: Record<string, boolean | string>;
  truth_boundary?: string;
  authority?: string;
}

export function useLiveAttention(projectId: string | null) {
  const [attention, setAttention] = useState<AttentionLens | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setAttention(null);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    if (!projectId) {
      setAttention(null);
      setDataSource(null);
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    liveApiFetch(`/v1/attention?project=${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`attention HTTP ${response.status}`);
        }
        return (await response.json()) as AttentionLens;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setAttention(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setAttention(null);
        setDataSource(null);
        setError(exc instanceof Error ? exc.message : "attention unavailable");
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

  return { attention, error, loading, dataSource };
}
