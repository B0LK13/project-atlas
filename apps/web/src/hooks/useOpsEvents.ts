import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/** LIVE_API ops-events; demo fallback is honest unknown (no invented events). */

export interface OpsEventRow {
  event_id?: string;
  sequence?: number;
  event_uid?: string;
  severity?: string;
  truth_plane?: string;
  authority_plane?: string;
}

export interface OpsEventsView {
  package_id?: string;
  available?: boolean;
  status?: string;
  reason?: string;
  reason_code?: string;
  stream_present?: boolean;
  event_count?: number;
  returned_count?: number;
  truncated?: boolean;
  events?: OpsEventRow[];
  honesty?: Record<string, boolean | string>;
  data_source?: DataSource;
  demo_isolated?: boolean;
}

const EMPTY_UNKNOWN: OpsEventsView = {
  package_id: "AS-CODER-ALPHA-OPS-EVENTS-READ-001",
  available: false,
  status: "UNKNOWN",
  reason: "DEMO STUB — no live vault; ops events are not invented.",
  reason_code: "DEMO_STUB_UNKNOWN",
  stream_present: false,
  event_count: 0,
  returned_count: 0,
  truncated: false,
  events: [],
  honesty: {
    lens_is_authority: false,
    unknown_is_healthy: false,
    fabricated_events: false,
    authentic_pilot: false,
  },
  data_source: "demo_stub",
  demo_isolated: true,
};

export function useOpsEvents(): {
  view: OpsEventsView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [view, setView] = useState<OpsEventsView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const resp = await liveApiFetch("/v1/ops/events?limit=50");
          if (resp.ok) {
            const body = (await resp.json()) as OpsEventsView;
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
            setError(`ops-events HTTP ${resp.status}`);
            setView(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(
              err instanceof Error ? err.message : "ops-events load failed",
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
          setError(err instanceof Error ? err.message : "ops-events load failed");
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
