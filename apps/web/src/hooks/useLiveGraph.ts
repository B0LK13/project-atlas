import { useEffect, useState } from "react";
import {
  LiveApiAuthError,
  liveApiDemoOnly,
  liveApiFetch,
} from "../api/liveApi";
import type { DataSource } from "../types";

/** AS-2.1-WEB-LIVE deepen: LIVE_API graph summary first; demo-isolated unknown fallback. */

export interface GraphSummaryView {
  authority?: string;
  node_count?: number;
  edge_count?: number;
  available?: boolean;
  note?: string;
  [key: string]: unknown;
}

export function useLiveGraph(): {
  graph: GraphSummaryView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [graph, setGraph] = useState<GraphSummaryView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const resp = await liveApiFetch("/v1/graph");
          if (resp.ok) {
            const body = (await resp.json()) as GraphSummaryView;
            if (!cancelled) {
              setGraph({ ...body, authority: "derived" });
              setDataSource("live_api");
              setError(null);
            }
            return;
          }
        } catch (err: unknown) {
          // SEC-SCAN-C-001: missing Bearer must fail closed — never silent demo.
          if (err instanceof LiveApiAuthError) {
            if (!cancelled) {
              setError(err.message);
              setGraph(null);
              setDataSource(null);
            }
            return;
          }
          // network / other: fall through to isolated demo empty
        }
      }
      if (!cancelled) {
        setGraph(null);
        setDataSource("demo_stub");
        setError(null);
      }
    }

    load()
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "graph load failed");
          setGraph(null);
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

  return { graph, error, loading, dataSource };
}
