import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface DoctorCheck {
  name?: string;
  status?: string;
  detail?: string;
}

export interface DoctorReport {
  package_id?: string;
  rollup?: string;
  ok?: boolean;
  check_count?: number;
  checks?: DoctorCheck[];
  available?: boolean;
  honesty?: Record<string, boolean | string>;
}

export function useLiveDoctor() {
  const [report, setReport] = useState<DoctorReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setReport(null);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    liveApiFetch("/v1/doctor")
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`doctor HTTP ${response.status}`);
        }
        return (await response.json()) as DoctorReport;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setReport(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setReport(null);
        setDataSource(null);
        setError(exc instanceof Error ? exc.message : "doctor unavailable");
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
