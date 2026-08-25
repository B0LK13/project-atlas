import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** LIVE_API inventory-drift lens; demo fallback is honest unknown. */

export interface InventoryDriftProject {
  project_id?: string;
  available?: boolean;
  status?: string;
  reason?: string;
  reason_code?: string;
  changed_paths?: string[];
}

export interface InventoryDriftView {
  package_id?: string;
  available?: boolean;
  status?: string;
  reason?: string;
  reason_code?: string;
  scoped?: boolean;
  project_id?: string;
  project_count?: number;
  changed_paths?: string[];
  projects?: InventoryDriftProject[];
  honesty?: Record<string, boolean | string>;
  data_source?: DataSource;
  demo_isolated?: boolean;
}

const EMPTY_UNKNOWN: InventoryDriftView = {
  package_id: "AS-CODER-ALPHA-INVENTORY-DRIFT-READ-001",
  available: false,
  status: "UNKNOWN",
  reason: "DEMO STUB — no live vault; inventory freshness is not invented.",
  reason_code: "DEMO_STUB_UNKNOWN",
  scoped: false,
  project_count: 0,
  changed_paths: [],
  projects: [],
  honesty: {
    lens_is_authority: false,
    stale_is_current: false,
    unknown_is_fresh: false,
    unknown_is_healthy: false,
    authentic_pilot: false,
    owner_capability_granted: false,
    demo_is_authentic: false,
  },
  data_source: "demo_stub",
  demo_isolated: true,
};

export function useInventoryDrift(projectId: string | null): {
  view: InventoryDriftView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [view, setView] = useState<InventoryDriftView | null>(null);
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
          const resp = await liveApiFetch(`/v1/inventory-drift${suffix}`);
          if (resp.ok) {
            const body = (await resp.json()) as InventoryDriftView;
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
            setError(`inventory-drift HTTP ${resp.status}`);
            setView(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(
              err instanceof Error ? err.message : "inventory-drift load failed",
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
            err instanceof Error ? err.message : "inventory-drift load failed",
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
