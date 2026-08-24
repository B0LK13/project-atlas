import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface SourceHealthRow {
  source?: string;
  source_id?: string | null;
  status?: string;
  pipeline_stage?: string;
  reason_code?: string;
  human_explanation?: string;
  evidence?: string;
  suggested_next_action?: string;
}

export interface SourceHealthLens {
  project_id?: string;
  health_state?: string;
  diagnostic?: string;
  actionable_count?: number;
  noise_count?: number;
  unscoped_omitted_count?: number;
  summary?: {
    health_state?: string;
    action_required?: number;
    excluded_informational?: number;
  };
  actionable?: SourceHealthRow[];
  noise?: SourceHealthRow[];
  honesty?: Record<string, boolean | string>;
  truth_boundary?: string;
  authority?: string;
}

const DEMO_STUB: SourceHealthLens = {
  project_id: undefined,
  health_state: "UNKNOWN",
  diagnostic: "unknown",
  actionable_count: 0,
  noise_count: 0,
  actionable: [],
  noise: [],
  honesty: {
    unknown_is_valid: true,
    lens_is_authority: false,
    unreadable_as_healthy: false,
    secrets_echoed: false,
  },
  truth_boundary: "SOURCE HEALTH != AUTHORITY / DEMO STUB ISOLATED",
  authority: "derived",
};

export function useLiveSourceHealth(projectId: string | null) {
  const [report, setReport] = useState<SourceHealthLens | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setReport(DEMO_STUB);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    if (!projectId) {
      setReport(null);
      setDataSource(null);
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    liveApiFetch(`/v1/source-health?project=${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`source-health HTTP ${response.status}`);
        }
        return (await response.json()) as SourceHealthLens;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setReport(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setReport(null);
        setDataSource(null);
        setError(exc instanceof Error ? exc.message : "source-health unavailable");
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

  return { report, error, loading, dataSource };
}
