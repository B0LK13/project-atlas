import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface InboxItem {
  receipt_id?: string;
  project_id?: string;
  status?: string;
  summary?: string;
  review_state?: string;
  item_count?: number;
  source_kind?: string;
}

export interface InboxLens {
  project_id?: string;
  status?: string;
  count?: number;
  items?: InboxItem[];
  unknown?: string | null;
  honesty?: Record<string, boolean | string>;
  truth_boundary?: string;
  authority?: string;
}

export function useLiveInbox(projectId: string | null) {
  const [inbox, setInbox] = useState<InboxLens | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setInbox(null);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    if (!projectId) {
      setInbox(null);
      setDataSource(null);
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    liveApiFetch(`/v1/inbox?project=${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`inbox HTTP ${response.status}`);
        }
        return (await response.json()) as InboxLens;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setInbox(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setInbox(null);
        setDataSource(null);
        setError(exc instanceof Error ? exc.message : "inbox unavailable");
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

  return { inbox, error, loading, dataSource };
}
