import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface HandoffHonesty {
  lens_is_authority?: boolean;
  mcp_is_authority?: boolean;
  authentic_pilot?: boolean;
  atlas_opt_wake_gate?: string;
}

export interface HandoffSummary {
  handoff_id?: string;
  project_id?: string;
  path?: string;
  purpose?: string;
  operator_note?: string | null;
  latest?: boolean;
  authority?: boolean;
  honesty?: HandoffHonesty;
}

export interface HandoffLatest {
  handoff_id?: string;
  path?: string;
  project_id?: string | null;
}

export interface HandoffInventory {
  package_id?: string;
  project_id?: string | null;
  handoff_count?: number;
  handoffs?: HandoffSummary[];
  latest?: HandoffLatest | null;
  available?: boolean;
  honesty?: Record<string, boolean | string>;
}

export function useLiveHandoffs(projectId: string | null) {
  const [inventory, setInventory] = useState<HandoffInventory | null>(null);
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
      ? `/v1/handoffs?project=${encodeURIComponent(projectId)}`
      : "/v1/handoffs";
    setLoading(true);
    liveApiFetch(path)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`handoffs HTTP ${response.status}`);
        }
        return (await response.json()) as HandoffInventory;
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
        setError(exc instanceof Error ? exc.message : "handoffs unavailable");
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
