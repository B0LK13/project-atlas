import { useEffect, useState } from "react";
import {
  LiveApiAuthError,
  liveApiDemoOnly,
  liveApiFetch,
} from "../api/liveApi";
import type { DataSource } from "../types";

export interface RoadmapBlocker {
  reason?: string;
  waiting_on?: string | null;
  unlock_condition?: string | null;
}

export interface RoadmapItem {
  id: string;
  title: string;
  status: string;
  critical_path?: boolean;
  missing_acceptance_evidence?: boolean;
  blockers?: RoadmapBlocker[];
}

export interface RoadmapLens {
  project_id?: string;
  status?: string;
  summary?: string | null;
  you_are_here?: {
    item_id?: string | null;
    title?: string;
    status?: string;
    lifecycle?: string;
    reason?: string;
    why?: string;
  };
  next_unlock?: {
    item_id?: string | null;
    title?: string;
    status?: string;
    lifecycle?: string;
    waiting_on?: string | null;
    unlock_condition?: string | null;
    reason?: string;
    why?: string;
  };
  critical_path?: string[];
  items?: RoadmapItem[];
  blockers?: RoadmapBlocker[];
  unknowns?: string[];
  honesty?: Record<string, boolean | string>;
}

export function useLiveRoadmap(projectId: string | null) {
  const [roadmap, setRoadmap] = useState<RoadmapLens | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!projectId || liveApiDemoOnly()) {
      setRoadmap(null);
      setDataSource("demo_stub");
      setError(null);
      return;
    }
    setLoading(true);
    liveApiFetch(`/v1/roadmap?project=${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`roadmap ${response.status}`);
        }
        return (await response.json()) as RoadmapLens;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setRoadmap(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setRoadmap(null);
        setDataSource("demo_stub");
        if (exc instanceof LiveApiAuthError) {
          setError(exc.message);
          return;
        }
        setError(exc instanceof Error ? exc.message : "roadmap unavailable");
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

  return { roadmap, error, loading, dataSource };
}
