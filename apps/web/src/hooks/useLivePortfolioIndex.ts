import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource, ProjectSummary } from "../types";
import { useReadStatus } from "./useReadStatus";

/** AS-CODER-ALPHA-PORTFOLIO-INDEX-001 — vault-scoped portfolio cards. */

const PACKAGE_ID = "AS-CODER-ALPHA-PORTFOLIO-INDEX-001" as const;
const PROJECT_ID_RE = /^[a-z][a-z0-9-]{0,63}$/;

export interface PortfolioIndexRow {
  project_id: string;
  path: string | null;
  included: boolean;
}

export interface PortfolioIndex {
  schema_version: 1;
  package_id: "AS-CODER-ALPHA-PORTFOLIO-INDEX-001";
  project_count: number;
  included_ids: string[];
  skipped_invalid_ids: string[];
  rows: PortfolioIndexRow[];
  portfolio: Record<string, unknown> | null;
  available: boolean;
  honesty: {
    ui_is_canonical: false;
    portfolio_is_authority: false;
    mcp_is_authority: false;
    unknown_is_valid: true;
    fabricated_fields: false;
    request_contains_project: false;
    zero_arg_vault_scope: true;
    portfolio_implicit_all: false;
    empty_arg_portfolio_state: false;
    owner_capability_granted: false;
    authentic_pilot: false;
  };
}

function emptyIndex(): PortfolioIndex {
  return {
    schema_version: 1,
    package_id: PACKAGE_ID,
    project_count: 0,
    included_ids: [],
    skipped_invalid_ids: [],
    rows: [],
    portfolio: null,
    available: false,
    honesty: {
      ui_is_canonical: false,
      portfolio_is_authority: false,
      mcp_is_authority: false,
      unknown_is_valid: true,
      fabricated_fields: false,
      request_contains_project: false,
      zero_arg_vault_scope: true,
      portfolio_implicit_all: false,
      empty_arg_portfolio_state: false,
      owner_capability_granted: false,
      authentic_pilot: false,
    },
  };
}

function projectRows(projects: ProjectSummary[]): ProjectSummary[] {
  const seen = new Set<string>();
  const rows: ProjectSummary[] = [];
  for (const project of projects) {
    const id = (project.project_id || "").trim();
    if (!id || seen.has(id)) {
      continue;
    }
    seen.add(id);
    rows.push(project);
  }
  rows.sort((a, b) => a.project_id.localeCompare(b.project_id));
  return rows;
}

function classify(projects: ProjectSummary[]): {
  included: string[];
  skipped: string[];
  rows: PortfolioIndexRow[];
} {
  const included: string[] = [];
  const skipped: string[] = [];
  const rows: PortfolioIndexRow[] = [];
  for (const project of projects) {
    const ok = PROJECT_ID_RE.test(project.project_id);
    rows.push({
      project_id: project.project_id,
      path: project.path ?? null,
      included: ok,
    });
    if (ok) {
      included.push(project.project_id);
    } else {
      skipped.push(project.project_id);
    }
  }
  return { included, skipped, rows };
}

async function loadPortfolio(
  projectIds: string[],
): Promise<{ portfolio: Record<string, unknown> | null; error: string | null }> {
  if (projectIds.length === 0) {
    return { portfolio: null, error: null };
  }
  const query = projectIds
    .map((id) => `project=${encodeURIComponent(id)}`)
    .join("&");
  try {
    const resp = await liveApiFetch(`/v1/portfolio-state?${query}`);
    if (!resp.ok) {
      return { portfolio: null, error: `portfolio HTTP ${resp.status}` };
    }
    const body = (await resp.json()) as Record<string, unknown>;
    return { portfolio: body, error: null };
  } catch (err: unknown) {
    return {
      portfolio: null,
      error: err instanceof Error ? err.message : "portfolio load failed",
    };
  }
}

export function useLivePortfolioIndex(): {
  index: PortfolioIndex;
  error: string | null;
  loading: boolean;
  dataSource: DataSource | null;
} {
  const {
    status,
    error: statusError,
    loading: statusLoading,
    dataSource: statusSource,
  } = useReadStatus();
  const [index, setIndex] = useState<PortfolioIndex>(emptyIndex);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [dataSource, setDataSource] = useState<DataSource | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load(): Promise<void> {
      if (statusLoading) {
        setLoading(true);
        return;
      }
      const projects = projectRows(status?.projects ?? []);
      const classified = classify(projects);
      if (liveApiDemoOnly() || statusSource === "demo_stub") {
        if (!cancelled) {
          const stub = emptyIndex();
          stub.project_count = projects.length;
          stub.included_ids = classified.included;
          stub.skipped_invalid_ids = classified.skipped;
          stub.rows = classified.rows;
          stub.portfolio = null;
          stub.available = false;
          setIndex(stub);
          setDataSource("demo_stub");
          setError(statusError);
          setLoading(false);
        }
        return;
      }
      if (statusSource !== "live_api") {
        if (!cancelled) {
          setIndex(emptyIndex());
          setDataSource(statusSource);
          setError(statusError);
          setLoading(false);
        }
        return;
      }
      setLoading(true);
      const { portfolio, error: portfolioError } = await loadPortfolio(
        classified.included,
      );
      if (cancelled) {
        return;
      }
      const next = emptyIndex();
      next.project_count = projects.length;
      next.included_ids = classified.included;
      next.skipped_invalid_ids = classified.skipped;
      next.rows = classified.rows;
      next.portfolio = portfolio;
      next.available = portfolio != null;
      setIndex(next);
      setDataSource("live_api");
      setError(portfolioError ?? statusError);
      setLoading(false);
    }

    load().catch((err: unknown) => {
      if (!cancelled) {
        setIndex(emptyIndex());
        setDataSource(null);
        setError(err instanceof Error ? err.message : "portfolio index failed");
        setLoading(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [status, statusError, statusLoading, statusSource]);

  return { index, error, loading, dataSource };
}
