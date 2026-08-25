import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export type ProjectStateLens = Record<string, unknown>;

export function useLiveProjectState(projectId: string | null) {
  const [state, setState] = useState<ProjectStateLens | null>(null);
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
    liveApiFetch(`/v1/project-state?project=${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`project-state HTTP ${response.status}`);
        }
        return (await response.json()) as ProjectStateLens;
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
        setError(exc instanceof Error ? exc.message : "project-state unavailable");
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
