import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface ObsidianNote {
  project_id?: string;
  path?: string;
  has_human_notes?: boolean;
  has_generated_markers?: boolean;
  authority?: boolean;
  plugin_shipped?: boolean;
}

export interface ObsidianInventory {
  package_id?: string;
  project_id?: string | null;
  note_count?: number;
  notes?: ObsidianNote[];
  available?: boolean;
  honesty?: Record<string, boolean | string>;
}

export function useLiveObsidian(projectId: string | null) {
  const [inventory, setInventory] = useState<ObsidianInventory | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setInventory(null);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    const path = projectId
      ? `/v1/obsidian?project=${encodeURIComponent(projectId)}`
      : "/v1/obsidian";
    setLoading(true);
    liveApiFetch(path)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`obsidian HTTP ${response.status}`);
        }
        return (await response.json()) as ObsidianInventory;
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setInventory(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setInventory(null);
        setDataSource(null);
        setError(exc instanceof Error ? exc.message : "obsidian unavailable");
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

  return { inventory, error, loading, dataSource };
}
