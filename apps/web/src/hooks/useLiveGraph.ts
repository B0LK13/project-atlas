import { useEffect, useState } from "react";
import type { DataSource } from "../types";

/** AS-2.1-WEB-LIVE deepen: LIVE_API graph summary first; demo-isolated unknown fallback. */

function envFlag(name: string): string | undefined {
  const env = (import.meta as ImportMeta & { env?: Record<string, string> }).env;
  return env?.[name];
}

function apiBase(): string {
  return (envFlag("VITE_ATLAS_API_BASE") ?? "http://127.0.0.1:8765").replace(/\/$/, "");
}

function demoOnly(): boolean {
  const raw = (envFlag("VITE_ATLAS_DEMO_ONLY") ?? "").trim().toLowerCase();
  return raw === "1" || raw === "true" || raw === "yes";
}

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
      if (!demoOnly()) {
        try {
          const resp = await fetch(`${apiBase()}/v1/graph`);
          if (resp.ok) {
            const body = (await resp.json()) as GraphSummaryView;
            if (!cancelled) {
              setGraph({ ...body, authority: "derived" });
              setDataSource("live_api");
              setError(null);
            }
            return;
          }
        } catch {
          // fall through
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
