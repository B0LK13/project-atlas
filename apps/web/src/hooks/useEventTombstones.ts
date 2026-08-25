import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** LIVE_API event-tombstone lens; demo fallback is honest unknown. */

export interface EventTombstoneRow {
  unit_key?: string;
  project_id?: string;
  event_id?: string;
  reason?: string;
  state?: string;
  deleted_paths?: string[];
}

export interface EventTombstonesView {
  package_id?: string;
  available?: boolean;
  status?: string;
  reason?: string;
  reason_code?: string;
  scoped?: boolean;
  project_id?: string;
  index_present?: boolean;
  deleted_count?: number;
  tombstones?: EventTombstoneRow[];
  honesty?: Record<string, boolean | string>;
  data_source?: DataSource;
  demo_isolated?: boolean;
}

const EMPTY_UNKNOWN: EventTombstonesView = {
  package_id: "AS-CODER-ALPHA-EVENT-TOMBSTONES-READ-001",
  available: false,
  status: "UNKNOWN",
  reason: "DEMO STUB — no live vault; deletions are not invented as empty or healthy.",
  reason_code: "DEMO_STUB_UNKNOWN",
  scoped: false,
  index_present: false,
  deleted_count: 0,
  tombstones: [],
  honesty: {
    lens_is_authority: false,
    deleted_is_vanished: false,
    empty_is_healthy: false,
    unknown_is_clean: false,
    unknown_is_healthy: false,
    authentic_pilot: false,
    owner_capability_granted: false,
    demo_is_authentic: false,
  },
  data_source: "demo_stub",
  demo_isolated: true,
};

export function useEventTombstones(projectId: string | null): {
  view: EventTombstonesView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [view, setView] = useState<EventTombstonesView | null>(null);
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
          const resp = await liveApiFetch(`/v1/event-tombstones${suffix}`);
          if (resp.ok) {
            const body = (await resp.json()) as EventTombstonesView;
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
            setError(`event-tombstones HTTP ${resp.status}`);
            setView(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(
              err instanceof Error ? err.message : "event-tombstones load failed",
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
            err instanceof Error ? err.message : "event-tombstones load failed",
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
