import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource } from "../types";

export type IntelligenceView =
  | "overview"
  | "evidence"
  | "contradictions"
  | "state"
  | "attention"
  | "portfolio"
  | "decision";

export type IntelligenceHonesty =
  | "LIVE"
  | "DERIVED"
  | "UNKNOWN"
  | "NO_DATA"
  | "VALID_EMPTY"
  | "NO_MATCH"
  | "CONTESTED"
  | "STALE"
  | "HTTP_FAILURE"
  | "DEMO"
  | "MALFORMED_INPUT"
  | "UNSUPPORTED_SCOPE";

export interface IntelligenceBundle {
  evidence: Record<string, unknown> | null;
  conflicts: Record<string, unknown> | null;
  explain: Record<string, unknown> | null;
  state: Record<string, unknown> | null;
  attention: Record<string, unknown> | null;
  portfolio: Record<string, unknown> | null;
  change: Record<string, unknown> | null;
  context: Record<string, unknown> | null;
  gapPriority: Record<string, unknown> | null;
  dependencies: Record<string, unknown> | null;
  decision: Record<string, unknown> | null;
}

const EMPTY: IntelligenceBundle = {
  evidence: null,
  conflicts: null,
  explain: null,
  state: null,
  attention: null,
  portfolio: null,
  change: null,
  context: null,
  gapPriority: null,
  dependencies: null,
  decision: null,
};

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" ? (value as Record<string, unknown>) : {};
}

function honestyFromPayload(payload: Record<string, unknown> | null): string | null {
  if (!payload) {
    return null;
  }
  const honesty = payload.honesty;
  return typeof honesty === "string" ? honesty : null;
}

export function classifyIntelligenceTruth(args: {
  dataSource: DataSource | null;
  error: string | null;
  demoSelected: boolean;
  payloads: Array<Record<string, unknown> | null>;
}): IntelligenceHonesty {
  if (args.demoSelected) {
    return "DEMO";
  }
  if (args.error || args.dataSource === null) {
    return args.error ? "HTTP_FAILURE" : "UNKNOWN";
  }
  const classes = args.payloads
    .map((item) => honestyFromPayload(item))
    .filter((item): item is string => Boolean(item));
  if (classes.includes("CONTESTED")) {
    return "CONTESTED";
  }
  if (classes.includes("STALE")) {
    return "STALE";
  }
  if (classes.includes("NO_DATA") && classes.every((item) => item === "NO_DATA")) {
    return "NO_DATA";
  }
  if (classes.includes("MALFORMED_INPUT")) {
    return "MALFORMED_INPUT";
  }
  if (classes.includes("UNKNOWN")) {
    return "UNKNOWN";
  }
  if (classes.includes("DERIVED") || classes.includes("OBSERVED")) {
    return classes.includes("DERIVED") ? "DERIVED" : "LIVE";
  }
  if (args.dataSource === "live_api") {
    return "LIVE";
  }
  return "UNKNOWN";
}

async function readJson(path: string): Promise<Record<string, unknown>> {
  const response = await liveApiFetch(path);
  if (!response.ok) {
    const body = (await response.json().catch(() => ({}))) as Record<string, unknown>;
    const honesty = typeof body.honesty === "string" ? body.honesty : "HTTP_FAILURE";
    throw new Error(`intelligence HTTP ${response.status}:${honesty}`);
  }
  return asRecord(await response.json());
}

export function useLiveIntelligence(
  projectId: string | null,
  view: IntelligenceView,
) {
  const [bundle, setBundle] = useState<IntelligenceBundle>(EMPTY);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);
  const demoSelected = liveApiDemoOnly();

  useEffect(() => {
    let cancelled = false;
    if (demoSelected) {
      setBundle(EMPTY);
      setDataSource("demo_stub");
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    const needsProject = view !== "portfolio";
    if (needsProject && !projectId) {
      setBundle(EMPTY);
      setDataSource(null);
      setError(null);
      setLoading(false);
      return () => {
        cancelled = true;
      };
    }
    setLoading(true);
    const projectQ = projectId
      ? `project=${encodeURIComponent(projectId)}`
      : "";
    const jobs: Array<Promise<Partial<IntelligenceBundle>>> = [];
    if (projectId && view !== "portfolio") {
      jobs.push(
        readJson(`/v1/project-state?${projectQ}`).then((state) => ({ state })),
      );
      jobs.push(
        readJson(`/v1/intelligence/evidence?${projectQ}`).then((evidence) => ({
          evidence,
        })),
      );
      jobs.push(
        readJson(`/v1/intelligence/conflicts?${projectQ}`).then((conflicts) => ({
          conflicts,
        })),
      );
      jobs.push(
        readJson(`/v1/project-attention?${projectQ}`).then((attention) => ({
          attention,
        })),
      );
    }
    if (view === "overview" || view === "evidence" || view === "contradictions") {
      if (projectId) {
        jobs.push(
          readJson(
            `/v1/intelligence/explain?${projectQ}&field=datastore`,
          ).then((explain) => ({ explain })),
        );
      }
    }
    if (view === "overview" || view === "decision") {
      if (projectId) {
        jobs.push(
          readJson(
            `/v1/intelligence/query?${projectQ}&kind=decision`,
          ).then((decision) => ({ decision })),
        );
      }
    }
    if (view === "overview") {
      if (projectId) {
        jobs.push(
          readJson(`/v1/intelligence/query?${projectQ}&kind=change`).then(
            (change) => ({ change }),
          ),
        );
        jobs.push(
          readJson(`/v1/intelligence/query?${projectQ}&kind=context`).then(
            (context) => ({ context }),
          ),
        );
        jobs.push(
          readJson(
            `/v1/intelligence/query?${projectQ}&kind=gap-priority`,
          ).then((gapPriority) => ({ gapPriority })),
        );
        jobs.push(
          readJson(
            `/v1/intelligence/query?${projectQ}&kind=dependencies`,
          ).then((dependencies) => ({ dependencies })),
        );
      }
    }
    if (view === "overview" || view === "portfolio") {
      const portfolioPath = projectId
        ? `/v1/portfolio-state?${projectQ}`
        : "/v1/portfolio-state";
      jobs.push(readJson(portfolioPath).then((portfolio) => ({ portfolio })));
    }
    Promise.all(jobs)
      .then((parts) => {
        if (cancelled) {
          return;
        }
        const next = { ...EMPTY };
        for (const part of parts) {
          Object.assign(next, part);
        }
        setBundle(next);
        setDataSource("live_api");
        setError(null);
      })
      .catch((exc: unknown) => {
        if (cancelled) {
          return;
        }
        setBundle(EMPTY);
        setDataSource(null);
        setError(exc instanceof Error ? exc.message : "intelligence unavailable");
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, view, demoSelected]);

  const truth = classifyIntelligenceTruth({
    dataSource,
    error,
    demoSelected,
    payloads: [
      bundle.state,
      bundle.evidence,
      bundle.conflicts,
      bundle.attention,
      bundle.portfolio,
      bundle.decision,
    ],
  });

  return { bundle, error, loading, dataSource, truth, demoSelected };
}
