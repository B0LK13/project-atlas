import { useEffect, useState } from "react";
import type { DataSource } from "../types";

/** LIVE_API mission/workspace lenses; demo stub isolated; never invents PILOT rows. */

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

export interface LensView {
  rollup?: string;
  project_count?: number;
  knowledge_count?: number;
  mission_board_available?: boolean;
  workspace_board_available?: boolean;
  pilot_estate_rows?: unknown[];
  authentic_pilot?: boolean;
  data_source?: DataSource;
  demo_isolated?: boolean;
  note?: string;
  [key: string]: unknown;
}

function stampDemo(stub: LensView): LensView {
  return {
    ...stub,
    data_source: "demo_stub",
    demo_isolated: true,
    authentic_pilot: false,
    pilot_estate_rows: [],
    ui_canonical: false,
    graph_authority: false,
    unknown_equals_healthy: false,
  };
}

async function loadLens(path: string, stubUrl: string): Promise<{
  view: LensView;
  source: DataSource;
}> {
  if (!demoOnly()) {
    try {
      const resp = await fetch(`${apiBase()}${path}`);
      if (resp.ok) {
        const body = (await resp.json()) as LensView;
        return {
          view: {
            ...body,
            data_source: "live_api",
            demo_isolated: false,
            authentic_pilot: false,
            pilot_estate_rows: [],
          },
          source: "live_api",
        };
      }
    } catch {
      // fall through
    }
  }
  const stubResp = await fetch(stubUrl);
  if (!stubResp.ok) {
    throw new Error(`demo stub HTTP ${stubResp.status}`);
  }
  const stub = (await stubResp.json()) as LensView;
  return { view: stampDemo(stub), source: "demo_stub" };
}

function useLens(
  path: string,
  stubUrl: string,
): {
  view: LensView | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [view, setView] = useState<LensView | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loadLens(path, stubUrl)
      .then(({ view: payload, source }) => {
        if (!cancelled) {
          setView(payload);
          setDataSource(source);
          setError(null);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "lens load failed");
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
  }, [path, stubUrl]);

  return { view, error, loading, dataSource };
}

export function useLiveMission() {
  return useLens("/v1/mission", "/sample-mission-control.json");
}

export function useLiveWorkspace() {
  return useLens("/v1/workspace", "/sample-workspace.json");
}
