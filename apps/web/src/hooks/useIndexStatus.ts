import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** LIVE_API index-status; demo fallback is honest unknown (no invented indexes). */

export interface IndexRowView {
  name?: string;
  relative_path?: string;
  role?: string;
  presence?: string;
  id_count?: number | null;
}

export interface IndexStatusView {
  package_id?: string;
  available?: boolean;
  status?: string;
  reason?: string;
  reason_code?: string;
  required_present?: number;
  required_total?: number;
  legacy_indexes_present?: boolean;
  indexes?: IndexRowView[];
  honesty?: Record<string, boolean | string>;
  data_source?: DataSource;
  demo_isolated?: boolean;
}

const EMPTY_UNKNOWN: IndexStatusView = {
  package_id: "AS-CODER-ALPHA-INDEX-STATUS-001",
  available: false,
  status: "UNKNOWN",
  reason: "DEMO STUB — no live vault; index status is not invented.",
  reason_code: "DEMO_STUB_UNKNOWN",
  required_present: 0,
  required_total: 6,
  legacy_indexes_present: false,
  indexes: [],
  honesty: {
    lens_is_authority: false,
    unknown_is_healthy: false,
    fabricated_indexes: false,
    authentic_pilot: false,
  },
  data_source: "demo_stub",
  demo_isolated: true,
};

export function useIndexStatus(): {
  view: IndexStatusView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [view, setView] = useState<IndexStatusView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const resp = await liveApiFetch("/v1/index-status");
          if (resp.ok) {
            const body = (await resp.json()) as IndexStatusView;
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
            setError(`index-status HTTP ${resp.status}`);
            setView(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(
              err instanceof Error ? err.message : "index-status load failed",
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
            err instanceof Error ? err.message : "index-status load failed",
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
