import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** AS-CODER-ALPHA-WEB-001 / TRUTH-UX-001 — LIVE_API project brief + truth panel. */

export interface LensSection {
  answer_id?: string;
  title?: string;
  summary?: string;
  value_text?: string;
  path?: string;
  field?: string;
  status?: string;
  verified?: boolean;
  authority?: boolean;
}

export interface TruthPanel {
  package_id?: string;
  truth_boundary?: string;
  evidence?: Array<{
    path?: string;
    kind?: string;
    role?: string;
    authority?: boolean;
  }>;
  conflicts?: Array<{
    conflict_id?: string;
    subject?: string;
    field?: string;
    conflict_type?: string;
    claims?: Array<{ claim?: string; source_id?: string | null }>;
  }>;
  conflict_count?: number;
  pending_reviews?: Array<{
    review_id?: string;
    reason?: string;
    status?: string;
    path?: string;
  }>;
  pending_review_count?: number;
  human_decisions?: Array<{
    review_id?: string;
    decision?: string;
    reason?: string;
    verified?: boolean;
  }>;
  human_decision_count?: number;
  unknown?: {
    summary?: string;
    is_unknown?: boolean;
    healthy?: boolean;
  };
  labels?: Record<string, string>;
  confidence_theatre?: boolean;
}

export interface ProjectBrief {
  project_id?: string;
  purpose?: string;
  tech_stack?: string;
  architecture_summary?: string;
  current_state?: string;
  recent_meaningful_changes?: string;
  important_decisions?: string;
  unknown_or_conflicting?: string;
  suggested_next_work?: string[];
  evidence_links?: string[];
  available?: boolean;
  honesty?: Record<string, unknown>;
  lens_sections?: Record<string, LensSection | null | undefined>;
  session_captures?: Array<{
    capture_id?: string;
    kind?: string;
    summary?: string;
    source?: string;
    status?: string;
  }>;
  conversation_captures?: Array<{
    capture_id?: string;
    project_id?: string;
    source_provider?: string;
    summary?: string;
    review_state?: string;
    classification?: string;
    item_count?: number;
    status?: string;
    label?: string;
    authority?: boolean;
  }>;
  truth?: TruthPanel;
  truth_boundary?: string;
  brief_path?: string | null;
  [key: string]: unknown;
}

export function useLiveBrief(projectId: string | null): {
  brief: ProjectBrief | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [brief, setBrief] = useState<ProjectBrief | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(projectId));
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (!projectId) {
      setBrief(null);
      setError(null);
      setLoading(false);
      setDataSource(null);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const resp = await liveApiFetch(
            `/v1/brief?project=${encodeURIComponent(projectId as string)}`,
          );
          if (resp.ok) {
            const body = (await resp.json()) as ProjectBrief;
            if (!cancelled) {
              setBrief(body);
              setDataSource("live_api");
              setError(null);
            }
            return;
          }
          if (!cancelled) {
            setError(`brief HTTP ${resp.status}`);
            setBrief(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "brief load failed");
            setBrief(null);
            setDataSource(null);
          }
          return;
        }
      }
      if (!cancelled) {
        setBrief(null);
        setDataSource("demo_stub");
        setError(null);
      }
    }

    load()
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "brief load failed");
          setBrief(null);
          setDataSource(null);
        }
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

  return { brief, error, loading, dataSource };
}
