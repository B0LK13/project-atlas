import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface ConversationCaptureRow {
  capture_id?: string;
  project_id?: string;
  source_provider?: string;
  summary?: string;
  review_state?: string;
  authority?: boolean;
  item_count?: number;
  path?: string;
  status?: string;
}

export interface ConversationCaptureInventory {
  package_id?: string;
  project_id?: string | null;
  capture_count?: number;
  captures?: ConversationCaptureRow[];
  available?: boolean;
  honesty?: Record<string, boolean | string>;
}

export function useLiveConversationCaptures(projectId: string | null) {
  const [inventory, setInventory] = useState<ConversationCaptureInventory | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setInventory(null);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    const path = projectId
      ? `/v1/conversation-captures?project=${encodeURIComponent(projectId)}`
      : "/v1/conversation-captures";
    setLoading(true);
    liveApiFetch(path)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`conversation-captures HTTP ${response.status}`);
        }
        return (await response.json()) as ConversationCaptureInventory;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setInventory(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setInventory(null);
        setDataSource(null);
        setError(
          exc instanceof Error ? exc.message : "conversation captures unavailable",
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

  return { inventory, error, loading, dataSource };
}
