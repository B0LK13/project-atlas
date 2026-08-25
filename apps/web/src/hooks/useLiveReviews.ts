import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export interface PendingReview {
  review_id?: string;
  project_id?: string;
  subject?: string;
  field?: string;
  reason?: string;
  status?: string;
  path?: string;
  decided?: boolean;
}

export interface HumanDecision {
  review_id?: string;
  project_id?: string;
  decision?: string;
  reason?: string;
  status?: string;
  path?: string;
}

export interface ReviewInventory {
  package_id?: string;
  project_id?: string | null;
  pending_count?: number;
  pending_reviews?: PendingReview[];
  human_decision_count?: number;
  human_decisions?: HumanDecision[];
  available?: boolean;
  honesty?: Record<string, boolean | string>;
}

export function useLiveReviews(projectId: string | null) {
  const [inventory, setInventory] = useState<ReviewInventory | null>(null);
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
      ? `/v1/reviews?project=${encodeURIComponent(projectId)}`
      : "/v1/reviews";
    setLoading(true);
    liveApiFetch(path)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(`reviews HTTP ${response.status}`);
        }
        return (await response.json()) as ReviewInventory;
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
        setError(exc instanceof Error ? exc.message : "reviews unavailable");
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
