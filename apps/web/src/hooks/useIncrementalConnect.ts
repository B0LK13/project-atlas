import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** LIVE_API incremental-connect receipt; demo fallback is honest unknown. */

export interface IncrementalConnectView {
  package_id?: string;
  available?: boolean;
  status?: string;
  disposition?: string;
  reason?: string;
  reason_code?: string;
  receipt_present?: boolean;
  counters?: Record<string, number>;
  honesty?: Record<string, boolean | string>;
  data_source?: DataSource;
  demo_isolated?: boolean;
}

const EMPTY_UNKNOWN: IncrementalConnectView = {
  package_id: "AS-CODER-ALPHA-INCREMENTAL-CONNECT-READ-001",
  available: false,
  status: "UNKNOWN",
  disposition: "unknown",
  reason: "DEMO STUB — no live vault; incremental-connect skip is not invented.",
  reason_code: "DEMO_STUB_UNKNOWN",
  receipt_present: false,
  counters: {
    files_inspected: 0,
    content_changed: 0,
    semantic_records_changed: 0,
    physical_writes: 0,
    projections_regenerated: 0,
    ingest_invocations: 0,
    discover_invocations: 0,
  },
  honesty: {
    lens_is_authority: false,
    incremental_skip_is_authority: false,
    incremental_skip_is_validate: false,
    absent_is_skip: false,
    unknown_is_healthy: false,
    fabricated_skip: false,
    authentic_pilot: false,
    owner_capability_granted: false,
  },
  data_source: "demo_stub",
  demo_isolated: true,
};

export function useIncrementalConnect(): {
  view: IncrementalConnectView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [view, setView] = useState<IncrementalConnectView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const resp = await liveApiFetch("/v1/ops/incremental-connect");
          if (resp.ok) {
            const body = (await resp.json()) as IncrementalConnectView;
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
            setError(`incremental-connect HTTP ${resp.status}`);
            setView(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(
              err instanceof Error ? err.message : "incremental-connect load failed",
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
            err instanceof Error ? err.message : "incremental-connect load failed",
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
  }, []);

  return { view, error, loading, dataSource };
}
