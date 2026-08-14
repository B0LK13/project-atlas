import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface AskMatchProject {
  project_id?: string;
  path?: string;
  title?: string;
  name?: string;
}

export interface AskMatchKnowledge {
  subject?: string;
  answer_id?: string;
  field?: string;
  title?: string;
  summary?: string;
  value_text?: string;
}

export interface AskLiveAnswer {
  query?: string;
  live_ask?: boolean;
  canonical_write?: boolean;
  ui_truth?: boolean;
  graph_authority?: boolean;
  truth_boundary?: string;
  matches?: {
    projects?: AskMatchProject[];
    knowledge?: AskMatchKnowledge[];
    health_keywords?: string[];
  };
  health?: Record<string, unknown>;
}

export function useLiveAsk(query: string | null): {
  answer: AskLiveAnswer | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [answer, setAnswer] = useState<AskLiveAnswer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    const q = (query ?? "").trim();
    if (!q) {
      setAnswer(null);
      setError(null);
      setLoading(false);
      setDataSource(null);
      return () => {
        cancelled = true;
      };
    }
    if (q.length > 256) {
      setAnswer(null);
      setError("query too long (max 256)");
      setLoading(false);
      setDataSource(null);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly()) {
        try {
          const resp = await liveApiFetch(
            `/v1/ask?q=${encodeURIComponent(q)}`,
          );
          if (resp.ok) {
            const body = (await resp.json()) as AskLiveAnswer;
            if (!cancelled) {
              setAnswer(body);
              setDataSource("live_api");
              setError(null);
            }
            return;
          }
          if (!cancelled) {
            setError(`ask HTTP ${resp.status}`);
            setAnswer(null);
            setDataSource(null);
          }
          return;
        } catch (err: unknown) {
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "ask load failed");
            setAnswer(null);
            setDataSource(null);
          }
          return;
        }
      }
      if (!cancelled) {
        setAnswer(null);
        setDataSource("demo_stub");
        setError(null);
      }
    }

    load()
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [query]);

  return { answer, error, loading, dataSource };
}
