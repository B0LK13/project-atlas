import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001 — LIVE_API source-health; explicit project. */

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

export interface SourceHealthReport {
  project_id?: string;
  health_state?: string;
  diagnostic?: string;
  source_count?: number;
  actionable_count?: number;
  noise_count?: number;
  unscoped_omitted_count?: number;
  counts?: Record<string, number>;
  reason_counts?: Record<string, number>;
  noise_groups?: Record<string, number>;
  summary?: {
    health_state?: string;
    action_required?: number;
    excluded_informational?: number;
  };
  actionable?: SourceHealthRow[];
  noise?: SourceHealthRow[];
  artifact_status?: Record<string, string>;
  honesty?: Record<string, boolean | string>;
  truth_boundary?: string;
  authority?: string;
  api_package?: string;
  package?: string;
}

export function useLiveSourceHealth(projectId: string | null): {
  report: SourceHealthReport | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [report, setReport] = useState<SourceHealthReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setReport(null);
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
        return (await response.json()) as SourceHealthReport;
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
