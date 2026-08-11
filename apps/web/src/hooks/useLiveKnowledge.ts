import { useEffect, useState } from "react";
import {
  LiveApiAuthError,
  liveApiDemoOnly,
  liveApiFetch,
} from "../api/liveApi";
import type { DataSource } from "../types";

/** AS-2.1-WEB-LIVE deepen: LIVE_API knowledge first; demo-isolated empty fallback. */

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
      if (!liveApiDemoOnly()) {
        try {
          const resp = await liveApiFetch("/v1/knowledge?limit=100");
          if (resp.ok) {
            const body = (await resp.json()) as { knowledge?: KnowledgeRow[] };
            if (!cancelled) {
              setKnowledge(Array.isArray(body.knowledge) ? body.knowledge : []);
              setDataSource("live_api");
              setError(null);
            }
            return;
          }
        } catch (err: unknown) {
          if (err instanceof LiveApiAuthError) {
            if (!cancelled) {
              setError(err.message);
              setKnowledge([]);
              setDataSource(null);
            }
            return;
          }
          // network / other: fall through to isolated demo empty
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
