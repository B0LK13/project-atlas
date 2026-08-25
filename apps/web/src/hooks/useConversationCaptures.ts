import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** LIVE_API conversation-capture lens; demo fallback is honest unknown. */

export interface ConversationCaptureRow {
  capture_id?: string;
  project_id?: string;
  source_provider?: string;
  summary?: string;
  review_state?: string;
  item_count?: number;
  status?: string;
}

export interface ConversationCapturesView {
  package_id?: string;
  available?: boolean;
  status?: string;
  reason?: string;
  reason_code?: string;
  scoped?: boolean;
  project_id?: string;
  directory_present?: boolean;
  capture_count?: number;
  captures?: ConversationCaptureRow[];
  honesty?: Record<string, boolean | string>;
  data_source?: DataSource;
  demo_isolated?: boolean;
}

const EMPTY_UNKNOWN: ConversationCapturesView = {
  package_id: "AS-CODER-ALPHA-CONVERSATION-CAPTURES-READ-001",
  available: false,
  status: "UNKNOWN",
  reason: "DEMO STUB — no live vault; captures are not invented as empty or healthy.",
  reason_code: "DEMO_STUB_UNKNOWN",
  scoped: false,
  directory_present: false,
  capture_count: 0,
  captures: [],
  honesty: {
    lens_is_authority: false,
    capture_is_truth_core: false,
    reviewed_is_promoted: false,
    empty_is_healthy: false,
    unknown_is_clean: false,
    unknown_is_healthy: false,
    authentic_pilot: false,
    owner_capability_granted: false,
    demo_is_authentic: false,
  },
  data_source: "demo_stub",
  demo_isolated: true,
};

export function useConversationCaptures(projectId: string | null): {
  view: ConversationCapturesView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [view, setView] = useState<ConversationCapturesView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const suffix = projectId
            ? `?project=${encodeURIComponent(projectId)}`
            : "";
          const resp = await liveApiFetch(`/v1/conversation-captures${suffix}`);
          if (resp.ok) {
            const body = (await resp.json()) as ConversationCapturesView;
            if (!cancelled) {
              setView({
                ...body,
                data_source: "live_api",
                demo_isolated: false,
              });
              setDataSource("live_api");
              setError(null);
            }
            return;
          }
          if (!cancelled) {
            setError(`conversation-captures HTTP ${resp.status}`);
            setView(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(
              err instanceof Error
                ? err.message
                : "conversation-captures load failed",
            );
            setView(null);
            setDataSource(null);
          }
          return;
        }
      }
      if (!cancelled) {
        setView(EMPTY_UNKNOWN);
        setDataSource("demo_stub");
        setError(null);
      }
    }

    load()
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "conversation-captures load failed",
          );
          setView(null);
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

  return { view, error, loading, dataSource };
}
