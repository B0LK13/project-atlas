import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** LIVE_API revocations; demo fallback is honest unknown (no invented rows). */

export interface RevocationRow {
  unit_key?: string;
  project_id?: string;
  event_id?: string;
  reason?: string;
  status?: string;
  receipt_path?: string;
}

export interface RevocationsView {
  package_id?: string;
  available?: boolean;
  status?: string;
  reason?: string;
  reason_code?: string;
  index_present?: boolean;
  revocation_count?: number;
  returned_count?: number;
  truncated?: boolean;
  revocations?: RevocationRow[];
  honesty?: Record<string, boolean | string>;
  data_source?: DataSource;
  demo_isolated?: boolean;
}

const EMPTY_UNKNOWN: RevocationsView = {
  package_id: "AS-CODER-ALPHA-REVOCATIONS-READ-001",
  available: false,
  status: "UNKNOWN",
  reason: "DEMO STUB — no live vault; receipt revocations are not invented.",
  reason_code: "DEMO_STUB_UNKNOWN",
  index_present: false,
  revocation_count: 0,
  returned_count: 0,
  truncated: false,
  revocations: [],
  honesty: {
    lens_is_authority: false,
    unknown_is_healthy: false,
    fabricated_revocations: false,
    authentic_pilot: false,
    owner_capability_granted: false,
  },
  data_source: "demo_stub",
  demo_isolated: true,
};

export function useRevocations(): {
  view: RevocationsView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [view, setView] = useState<RevocationsView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const resp = await liveApiFetch("/v1/ops/revocations?limit=50");
          if (resp.ok) {
            const body = (await resp.json()) as RevocationsView;
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
            setError(`revocations HTTP ${resp.status}`);
            setView(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(
              err instanceof Error ? err.message : "revocations load failed",
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
          setError(err instanceof Error ? err.message : "revocations load failed");
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
