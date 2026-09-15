import { useEffect, useState } from "react";
import {
  LiveApiAuthError,
  liveApiDemoOnly,
  liveApiFetch,
} from "../api/liveApi";
import type { DataSource } from "../types";

/**
 * AS-2.2-KDIFF-001 web lens: LIVE_API conflict + Time Machine state for a
 * selected project. Golden-demo defaults remain harbor-api / T1→T2 when the
 * URL does not name a project. Read-only; kdiff ≠ authority.
 * Demo-isolated honest empty fallback — never invents conflicts or diffs.
 */

/** Golden demo defaults (must match the backend golden fixture). */
export const TIME_MACHINE_PROJECT = "harbor-api";
export const TIME_MACHINE_T1 = "2024-03-01";
export const TIME_MACHINE_T2 = "2024-10-01";

export interface ConflictClaim {
  claim: string;
  source_id: string | null;
}

export interface ConflictRow {
  conflict_id: string;
  subject: string;
  field: string;
  conflict_type: string;
  claims: ConflictClaim[];
}

export interface KdiffCell {
  subject: string;
  field: string;
  disposition: string;
  value_sketch?: string;
  authority_role?: string;
  freshness?: string;
  conflict_state?: string;
}

export interface DiffChange {
  subject: string;
  field: string;
  from_value_sketch: string;
  to_value_sketch: string;
}

export interface DiffAdded {
  subject: string;
  field: string;
  value_sketch?: string;
}

export interface DiffRemoved {
  subject: string;
  field: string;
}

export interface TimeMachineDiff {
  change_count: number;
  value_changed: DiffChange[];
  added: DiffAdded[];
  removed: DiffRemoved[];
}

interface ConflictsResponse {
  conflict_count?: number;
  conflicts?: ConflictRow[];
}

interface AsOfResponse {
  status?: string;
  cells?: KdiffCell[];
}

interface DiffResponse {
  change_count?: number;
  value_changed?: DiffChange[];
  added?: DiffAdded[];
  removed?: DiffRemoved[];
}

const EMPTY_DIFF: TimeMachineDiff = {
  change_count: 0,
  value_changed: [],
  added: [],
  removed: [],
};

export function useLiveTimeMachine(
  projectId: string | null = TIME_MACHINE_PROJECT,
  t1: string = TIME_MACHINE_T1,
  t2: string = TIME_MACHINE_T2,
): {
  conflicts: ConflictRow[];
  asOfT1Cells: KdiffCell[];
  asOfT2Cells: KdiffCell[];
  diff: TimeMachineDiff;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
  projectId: string | null;
  t1: string;
  t2: string;
} {
  const [conflicts, setConflicts] = useState<ConflictRow[]>([]);
  const [asOfT1Cells, setAsOfT1Cells] = useState<KdiffCell[]>([]);
  const [asOfT2Cells, setAsOfT2Cells] = useState<KdiffCell[]>([]);
  const [diff, setDiff] = useState<TimeMachineDiff>(EMPTY_DIFF);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    async function load(): Promise<void> {
      if (!liveApiDemoOnly() && projectId) {
        try {
          const project = encodeURIComponent(projectId);
          const from = encodeURIComponent(t1);
          const to = encodeURIComponent(t2);
          const [conflictsResp, asOfT1Resp, asOfT2Resp, diffResp] =
            await Promise.all([
              liveApiFetch(`/v1/conflicts?project=${project}`),
              liveApiFetch(`/v1/kdiff?project=${project}&as_of=${from}`),
              liveApiFetch(`/v1/kdiff?project=${project}&as_of=${to}`),
              liveApiFetch(
                `/v1/kdiff?project=${project}&from=${from}&to=${to}`,
              ),
            ]);
          if (!conflictsResp.ok || !asOfT1Resp.ok || !asOfT2Resp.ok || !diffResp.ok) {
            if (!cancelled) {
              setError(
                `time-machine HTTP ${conflictsResp.status}/${asOfT1Resp.status}/` +
                  `${asOfT2Resp.status}/${diffResp.status}`,
              );
              setConflicts([]);
              setAsOfT1Cells([]);
              setAsOfT2Cells([]);
              setDiff(EMPTY_DIFF);
              setDataSource(null);
            }
            return;
          }
          const conflictsBody = (await conflictsResp.json()) as ConflictsResponse;
            const asOfT1Body = (await asOfT1Resp.json()) as AsOfResponse;
            const asOfT2Body = (await asOfT2Resp.json()) as AsOfResponse;
            const diffBody = (await diffResp.json()) as DiffResponse;
            if (!cancelled) {
              setConflicts(
                Array.isArray(conflictsBody.conflicts)
                  ? conflictsBody.conflicts
                  : [],
              );
              setAsOfT1Cells(
                Array.isArray(asOfT1Body.cells) ? asOfT1Body.cells : [],
              );
              setAsOfT2Cells(
                Array.isArray(asOfT2Body.cells) ? asOfT2Body.cells : [],
              );
              setDiff({
                change_count:
                  typeof diffBody.change_count === "number"
                    ? diffBody.change_count
                    : 0,
                value_changed: Array.isArray(diffBody.value_changed)
                  ? diffBody.value_changed
                  : [],
                added: Array.isArray(diffBody.added) ? diffBody.added : [],
                removed: Array.isArray(diffBody.removed) ? diffBody.removed : [],
              });
              setDataSource("live_api");
              setError(null);
            }
            return;
        } catch (err: unknown) {
          if (err instanceof LiveApiAuthError) {
            if (!cancelled) {
              setError(err.message);
              setConflicts([]);
              setAsOfT1Cells([]);
              setAsOfT2Cells([]);
              setDiff(EMPTY_DIFF);
              setDataSource(null);
            }
            return;
          }
          if (!cancelled) {
            setError(err instanceof Error ? err.message : "time machine load failed");
            setConflicts([]);
            setAsOfT1Cells([]);
            setAsOfT2Cells([]);
            setDiff(EMPTY_DIFF);
            setDataSource(null);
          }
          return;
        }
      }
      if (!cancelled) {
        setConflicts([]);
        setAsOfT1Cells([]);
        setAsOfT2Cells([]);
        setDiff(EMPTY_DIFF);
        setDataSource(liveApiDemoOnly() ? "demo_stub" : null);
        setError(
          liveApiDemoOnly() || !projectId
            ? null
            : "LIVE_API unavailable — no invented Time Machine rows",
        );
      }
    }

    load()
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "time machine load failed",
          );
          setConflicts([]);
          setAsOfT1Cells([]);
          setAsOfT2Cells([]);
          setDiff(EMPTY_DIFF);
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
  }, [projectId, t1, t2]);

  return {
    conflicts,
    asOfT1Cells,
    asOfT2Cells,
    diff,
    error,
    loading,
    dataSource,
    projectId,
    t1,
    t2,
  };
}
