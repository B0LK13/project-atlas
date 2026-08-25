import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** LIVE_API vault validate. OK ≠ healthy ≠ authority ≠ PILOT. */

export interface ValidateFinding {
  rule_id?: string;
  finding_id?: string;
  severity?: string;
  path?: string;
  message?: string;
  [key: string]: unknown;
}

export interface ValidateView {
  package_id?: string;
  ok?: boolean;
  exit_code?: number;
  error_count?: number;
  finding_count?: number;
  markdown_files?: number;
  errors?: string[];
  findings?: ValidateFinding[];
  honesty?: Record<string, unknown>;
  [key: string]: unknown;
}

export function useLiveValidate(): {
  report: ValidateView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [report, setReport] = useState<ValidateView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const resp = await liveApiFetch("/v1/validate");
          if (resp.ok) {
            const body = (await resp.json()) as ValidateView;
            if (!cancelled) {
              setReport(body);
              setDataSource("live_api");
              setError(null);
            }
            return;
          }
          if (!cancelled) {
            setError(`validate HTTP ${resp.status}`);
            setReport(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "validate load failed");
            setReport(null);
            setDataSource(null);
          }
          return;
        }
      }
      if (!cancelled) {
        setReport(null);
        setDataSource("demo_stub");
        setError(null);
      }
    }

    load()
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "validate load failed");
          setReport(null);
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

  return { report, error, loading, dataSource };
}
