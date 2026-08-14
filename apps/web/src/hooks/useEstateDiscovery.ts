import { useEffect, useState } from "react";
import {
  LiveApiAuthError,
  liveApiDemoOnly,
  liveApiFetch,
} from "../api/liveApi";
import type { DataSource } from "../types";

export type DiscoveryCategoryKey =
  | "DISCOVERED_PROJECTS"
  | "NEW_KNOWLEDGE"
  | "AMBIGUOUS_MATCHES"
  | "UNMATCHED_KNOWLEDGE"
  | "IGNORED"
  | "CONNECTED";

export interface DiscoveryEvidenceRow {
  kind?: string;
  detail?: string;
  weight?: string;
}

export interface DiscoveryCandidateRow {
  candidate_id?: string;
  kind?: string;
  path?: string;
  display_name?: string;
  match_state?: string;
  category?: string;
  why_matched?: string[];
  why_connected?: string[];
  match_evidence?: DiscoveryEvidenceRow[];
  conflicting_evidence?: DiscoveryEvidenceRow[];
  required_review?: boolean;
  required_action?: string | null;
  knowledge_relation?: string | null;
  candidate_family?: string | null;
  matched_project_id?: string | null;
}

export interface EstateDiscoveryView {
  package_id?: string;
  truth_boundary?: string;
  present: boolean;
  authorized_root?: string | null;
  authorized_root_mode?: string | null;
  volume_root_authorized?: boolean;
  volume_root_kind?: string | null;
  counts?: {
    projects?: number;
    knowledge?: number;
    ignored?: number;
    required_review?: number;
    connected?: number;
  };
  scan?: {
    scan_complete?: boolean;
    truncation_reason?: string | null;
    truncation_causes?: string[];
    depth_limit_reached?: boolean;
    max_depth?: number | null;
    project_limit_reached?: boolean;
    knowledge_limit_reached?: boolean;
    permission_errors?: unknown[];
    candidate_selection_policy?: string | null;
    project_candidates_seen?: number | null;
    project_candidates_emitted?: number | null;
    project_candidates_suppressed?: number | null;
    knowledge_candidates_seen?: number | null;
    knowledge_candidates_emitted?: number | null;
    knowledge_candidates_suppressed?: number | null;
  };
  categories: Record<DiscoveryCategoryKey, DiscoveryCandidateRow[]>;
  primary_question?: string;
  note?: string;
  data_source?: DataSource;
  demo_isolated?: boolean;
}

const EMPTY: EstateDiscoveryView = {
  present: false,
  categories: {
    DISCOVERED_PROJECTS: [],
    NEW_KNOWLEDGE: [],
    AMBIGUOUS_MATCHES: [],
    UNMATCHED_KNOWLEDGE: [],
    IGNORED: [],
    CONNECTED: [],
  },
  scan: {
    scan_complete: false,
    truncation_reason: "report_absent",
  },
  primary_question: "What did Atlas find that I should care about?",
  note: "No discovery report loaded.",
  data_source: "demo_stub",
  demo_isolated: true,
};

export function useEstateDiscovery(): {
  view: EstateDiscoveryView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [view, setView] = useState<EstateDiscoveryView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      setError(null);
      if (liveApiDemoOnly()) {
        if (!cancelled) {
          setView(EMPTY);
          setDataSource("demo_stub");
          setLoading(false);
        }
        return;
      }
      try {
        const resp = await liveApiFetch("/v1/discovery");
        if (!resp.ok) {
          throw new Error(`discovery HTTP ${resp.status}`);
        }
        const payload = (await resp.json()) as EstateDiscoveryView;
        if (cancelled) return;
        setView({
          ...EMPTY,
          ...payload,
          categories: {
            ...EMPTY.categories,
            ...(payload.categories ?? {}),
          },
          scan: {
            ...EMPTY.scan,
            ...(payload.scan ?? {}),
          },
          data_source: "live_api",
          demo_isolated: false,
        });
        setDataSource("live_api");
      } catch (err) {
        if (cancelled) return;
        if (err instanceof LiveApiAuthError) {
          setError(err.message);
        } else {
          setError(err instanceof Error ? err.message : "discovery unavailable");
        }
        setView(EMPTY);
        setDataSource("demo_stub");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return { view, error, loading, dataSource };
}
