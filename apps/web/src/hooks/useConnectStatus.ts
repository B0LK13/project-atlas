import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** LIVE_API connect-status; demo fallback is honest unknown (no invented receipt). */

export interface ConnectReceiptView {
  presence?: string;
  status?: string | null;
  vault_id?: string | null;
  project_root?: string | null;
  bound_project_id?: string | null;
  projects?: string[];
  documents_ingested?: number | null;
  incremental_disposition?: string | null;
}

export interface IncrementalReceiptView {
  presence?: string;
  disposition?: string | null;
  operational_only?: boolean;
}

export interface ConnectStatusView {
  package_id?: string;
  available?: boolean;
  status?: string;
  reason?: string;
  reason_code?: string;
  connect_receipt?: ConnectReceiptView;
  incremental_receipt?: IncrementalReceiptView;
  honesty?: Record<string, boolean | string>;
  data_source?: DataSource;
  demo_isolated?: boolean;
}

const EMPTY_UNKNOWN: ConnectStatusView = {
  package_id: "AS-CODER-ALPHA-CONNECT-STATUS-001",
  available: false,
  status: "UNKNOWN",
  reason: "DEMO STUB — no live vault; connect status is not invented.",
  reason_code: "DEMO_STUB_UNKNOWN",
  connect_receipt: { presence: "absent", projects: [] },
  incremental_receipt: { presence: "absent", operational_only: true },
  honesty: {
    lens_is_authority: false,
    unknown_is_fresh: false,
    fabricated_receipt: false,
    authentic_pilot: false,
  },
  data_source: "demo_stub",
  demo_isolated: true,
};

export function useConnectStatus(): {
  view: ConnectStatusView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [view, setView] = useState<ConnectStatusView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const resp = await liveApiFetch("/v1/connect-status");
          if (resp.ok) {
            const body = (await resp.json()) as ConnectStatusView;
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
            setError(`connect-status HTTP ${resp.status}`);
            setView(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(
              err instanceof Error ? err.message : "connect-status load failed",
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
            err instanceof Error ? err.message : "connect-status load failed",
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
