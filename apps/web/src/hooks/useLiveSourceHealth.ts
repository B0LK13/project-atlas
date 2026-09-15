import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

/**
 * AS-CODER-ALPHA-SOURCE-HEALTH-WEB-001 — LIVE_API source-health lens.
 * Explicit ?project= only. No implicit portfolio-all. No secret echo.
 * health_state is an opaque string. UNKNOWN/UNREADABLE stay honest.
 * SOURCE HEALTH != AUTHORITY. UI != CANONICAL TRUTH.
 */

export interface SourceHealthRow {
  source?: string;
  source_id?: string | null;
  status?: string;
  pipeline_stage?: string;
  reason_code?: string;
  human_explanation?: string;
  evidence?: string;
  suggested_next_action?: string;
}

export interface SourceHealthReport {
  schema?: string;
  package?: string;
  api_package?: string;
  project_id?: string | null;
  diagnostic?: string;
  /** Opaque derived label from LIVE_API — do not invent an enum here. */
  health_state?: string;
  source_count?: number;
  actionable_count?: number;
  noise_count?: number;
  unscoped_omitted_count?: number;
  counts?: Record<string, number>;
  reason_counts?: Record<string, number>;
  noise_groups?: Record<string, number>;
  summary?: {
    health_state?: string;
    action_required?: number;
    excluded_informational?: number;
  };
  actionable?: SourceHealthRow[];
  noise?: SourceHealthRow[];
  artifact_status?: Record<string, string>;
  honesty?: Record<string, unknown>;
  authority?: string;
  truth_boundary?: string;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function asStringMap(value: unknown): Record<string, number> | undefined {
  const record = asRecord(value);
  if (!record) {
    return undefined;
  }
  const out: Record<string, number> = {};
  for (const [key, entry] of Object.entries(record)) {
    if (typeof entry === "number" && Number.isFinite(entry)) {
      out[key] = entry;
    }
  }
  return out;
}

function asRows(value: unknown): SourceHealthRow[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  return value.map((entry) => {
    const row = asRecord(entry) ?? {};
    return {
      source: asString(row.source),
      source_id: asString(row.source_id) ?? null,
      status: asString(row.status),
      pipeline_stage: asString(row.pipeline_stage),
      reason_code: asString(row.reason_code),
      human_explanation: asString(row.human_explanation),
      evidence: asString(row.evidence),
      suggested_next_action: asString(row.suggested_next_action),
    };
  });
}

function normalizeReport(payload: unknown): SourceHealthReport {
  const record = asRecord(payload) ?? {};
  const summary = asRecord(record.summary);
  const honesty = asRecord(record.honesty);
  return {
    schema: asString(record.schema),
    package: asString(record.package),
    api_package: asString(record.api_package),
    project_id: asString(record.project_id) ?? null,
    diagnostic: asString(record.diagnostic),
    health_state: asString(record.health_state),
    source_count: asNumber(record.source_count),
    actionable_count: asNumber(record.actionable_count),
    noise_count: asNumber(record.noise_count),
    unscoped_omitted_count: asNumber(record.unscoped_omitted_count),
    counts: asStringMap(record.counts),
    reason_counts: asStringMap(record.reason_counts),
    noise_groups: asStringMap(record.noise_groups),
    summary: summary
      ? {
          health_state: asString(summary.health_state),
          action_required: asNumber(summary.action_required),
          excluded_informational: asNumber(summary.excluded_informational),
        }
      : undefined,
    actionable: asRows(record.actionable),
    noise: asRows(record.noise),
    artifact_status: (() => {
      const status = asRecord(record.artifact_status);
      if (!status) {
        return undefined;
      }
      const out: Record<string, string> = {};
      for (const [key, entry] of Object.entries(status)) {
        const label = asString(entry);
        if (label) {
          out[key] = label;
        }
      }
      return out;
    })(),
    honesty: honesty ?? undefined,
    authority: asString(record.authority),
    truth_boundary: asString(record.truth_boundary),
  };
}

async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { error?: unknown; honesty?: unknown };
    const error = asString(body.error);
    const honesty = asString(body.honesty);
    if (error && honesty) {
      return `${error} (${honesty})`;
    }
    if (error) {
      return error;
    }
  } catch {
    // Body is not JSON — keep HTTP status only. Never echo raw bytes.
  }
  return `source-health HTTP ${response.status}`;
}

export function useLiveSourceHealth(projectId: string | null): {
  report: SourceHealthReport | null;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const [report, setReport] = useState<SourceHealthReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;
    if (liveApiDemoOnly()) {
      setReport(null);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    if (!projectId) {
      setReport(null);
      setDataSource(null);
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    liveApiFetch(`/v1/source-health?project=${encodeURIComponent(projectId)}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(await readErrorMessage(response));
        }
        return normalizeReport(await response.json());
      })
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setReport(payload);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setReport(null);
        setDataSource(null);
        setError(exc instanceof Error ? exc.message : "source-health unavailable");
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

  return { report, error, loading, dataSource };
}
