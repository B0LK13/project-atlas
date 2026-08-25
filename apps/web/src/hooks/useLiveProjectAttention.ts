import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export type ProjectAttentionLens = Record<string, unknown>;

export function useLiveProjectAttention(projectId: string | null) {
  const [attention, setAttention] = useState<ProjectAttentionLens | null>(null);
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
    liveApiFetch(`/v1/project-attention?project=${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`project-attention HTTP ${response.status}`);
        }
        return (await response.json()) as ProjectAttentionLens;
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
        setError(
          exc instanceof Error ? exc.message : "project-attention unavailable",
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

  return { attention, error, loading, dataSource };
}
