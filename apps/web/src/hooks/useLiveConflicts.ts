import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** Vault-scoped unresolved conflict index. Projection ≠ resolution. */

export interface ConflictClaimView {
  claim?: string;
  source_id?: string | null;
}

export interface ConflictRowView {
  conflict_id?: string;
  subject?: string;
  field?: string;
  conflict_type?: string;
  claims?: ConflictClaimView[];
}

export interface ConflictProjectView {
  project_id?: string;
  conflict_count?: number;
  conflicts?: ConflictRowView[];
  available?: boolean;
}

export interface ConflictIndexView {
  package_id?: string;
  project_count?: number;
  conflict_count?: number;
  projects?: ConflictProjectView[];
  authority?: string;
  honesty?: Record<string, unknown>;
  [key: string]: unknown;
}

export function useLiveConflicts(): {
  index: ConflictIndexView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [index, setIndex] = useState<ConflictIndexView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const resp = await liveApiFetch("/v1/conflicts");
          if (resp.ok) {
            const body = (await resp.json()) as ConflictIndexView;
            if (!cancelled) {
              setIndex({ ...body, authority: "derived" });
              setDataSource("live_api");
              setError(null);
            }
            return;
          }
          if (!cancelled) {
            setError(`conflicts HTTP ${resp.status}`);
            setIndex(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "conflicts load failed");
            setIndex(null);
            setDataSource(null);
          }
          return;
        }
      }
      if (!cancelled) {
        setIndex(null);
        setDataSource("demo_stub");
        setError(null);
      }
    }

    load()
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "conflicts load failed");
          setIndex(null);
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

  return { index, error, loading, dataSource };
}
