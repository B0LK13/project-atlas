import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** LIVE_API web action ledger. Ledger ≠ Truth Core. GET ≠ POST. */

export interface ActionLedgerView {
  package_id?: string;
  transactions?: Array<Record<string, unknown>>;
  truth_boundary?: string;
  [key: string]: unknown;
}

export function useLiveActions(): {
  ledger: ActionLedgerView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [ledger, setLedger] = useState<ActionLedgerView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const resp = await liveApiFetch("/v1/actions");
          if (resp.ok) {
            const body = (await resp.json()) as ActionLedgerView;
            if (!cancelled) {
              setLedger(body);
              setDataSource("live_api");
              setError(null);
            }
            return;
          }
          if (!cancelled) {
            setError(`actions HTTP ${resp.status}`);
            setLedger(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "actions load failed");
            setLedger(null);
            setDataSource(null);
          }
          return;
        }
      }
      if (!cancelled) {
        setLedger(null);
        setDataSource("demo_stub");
        setError(null);
      }
    }

    load()
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "actions load failed");
          setLedger(null);
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

  return { ledger, error, loading, dataSource };
}
