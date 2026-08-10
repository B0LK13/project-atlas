import { useEffect, useState } from "react";
import type { DataSource } from "../types";

/** AS-2.1-WEB-LIVE deepen: LIVE_API knowledge first; demo-isolated empty fallback. */

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

export interface KnowledgeRow {
  subject?: string;
  answer_id?: string;
  title?: string;
  summary?: string;
  [key: string]: unknown;
}

export function useLiveKnowledge(): {
  knowledge: KnowledgeRow[];
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [knowledge, setKnowledge] = useState<KnowledgeRow[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!demoOnly()) {
        try {
          const resp = await fetch(`${apiBase()}/v1/knowledge?limit=100`);
          if (resp.ok) {
            const body = (await resp.json()) as { knowledge?: KnowledgeRow[] };
            if (!cancelled) {
              setKnowledge(Array.isArray(body.knowledge) ? body.knowledge : []);
              setDataSource("live_api");
              setError(null);
            }
            return;
          }
        } catch {
          // fall through to isolated demo empty
        }
      }
      if (!cancelled) {
        setKnowledge([]);
        setDataSource("demo_stub");
        setError(null);
      }
    }

    load()
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "knowledge load failed");
          setKnowledge([]);
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

  return { knowledge, error, loading, dataSource };
}
