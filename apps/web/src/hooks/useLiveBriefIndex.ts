import { useEffect, useState } from "react";
import { liveApiDemoOnly, liveApiFetch } from "../api/liveApi";
import type { DataSource, ProjectSummary } from "../types";
import type { ProjectBrief } from "./useLiveBrief";
import { useReadStatus } from "./useReadStatus";

/** AS-CODER-ALPHA-BRIEF-INDEX-WEB-001 — vault-scoped brief cards. */

export interface BriefIndexRow {
  project_id: string;
  path: string | null;
  brief: ProjectBrief | null;
  available: boolean;
  error: string | null;
}

export interface BriefIndex {
  schema_version: 1;
  package_id: "AS-CODER-ALPHA-BRIEF-INDEX-WEB-001";
  project_count: number;
  rows: BriefIndexRow[];
  honesty: {
    ui_is_canonical: false;
    brief_is_authority: false;
    mcp_is_authority: false;
    unknown_is_valid: true;
    fabricated_fields: false;
    request_contains_project: false;
    zero_arg_vault_scope: true;
    portfolio_implicit_all: false;
    owner_capability_granted: false;
    authentic_pilot: false;
  };
}

const PACKAGE_ID = "AS-CODER-ALPHA-BRIEF-INDEX-WEB-001" as const;

function emptyIndex(): BriefIndex {
  return {
    schema_version: 1,
    package_id: PACKAGE_ID,
    project_count: 0,
    rows: [],
    honesty: {
      ui_is_canonical: false,
      brief_is_authority: false,
      mcp_is_authority: false,
      unknown_is_valid: true,
      fabricated_fields: false,
      request_contains_project: false,
      zero_arg_vault_scope: true,
      portfolio_implicit_all: false,
      owner_capability_granted: false,
      authentic_pilot: false,
    },
  };
}

async function loadBrief(projectId: string): Promise<{
  brief: ProjectBrief | null;
  error: string | null;
}> {
  try {
    const resp = await liveApiFetch(
      `/v1/brief?project=${encodeURIComponent(projectId)}`,
    );
    if (!resp.ok) {
      return { brief: null, error: `brief HTTP ${resp.status}` };
    }
    const body = (await resp.json()) as ProjectBrief;
    return { brief: body, error: null };
  } catch (err: unknown) {
    return {
      brief: null,
      error: err instanceof Error ? err.message : "brief load failed",
    };
  }
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

export function useLiveBriefIndex(): {
  index: BriefIndex;
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
  const [index, setIndex] = useState<BriefIndex>(emptyIndex);
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
      if (liveApiDemoOnly() || statusSource === "demo_stub") {
        if (!cancelled) {
          const stub = emptyIndex();
          stub.project_count = projects.length;
          stub.rows = projects.map((project) => ({
            project_id: project.project_id,
            path: project.path ?? null,
            brief: null,
            available: false,
            error: null,
          }));
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
      const loaded = await Promise.all(
        projects.map(async (project) => {
          const { brief, error: briefError } = await loadBrief(project.project_id);
          const available = brief?.available === true;
          return {
            project_id: project.project_id,
            path: project.path ?? null,
            brief,
            available,
            error: briefError,
          } satisfies BriefIndexRow;
        }),
      );
      if (cancelled) {
        return;
      }
      const next = emptyIndex();
      next.project_count = loaded.length;
      next.rows = loaded;
      setIndex(next);
      setDataSource("live_api");
      setError(statusError);
      setLoading(false);
    }

    load().catch((err: unknown) => {
      if (!cancelled) {
        setIndex(emptyIndex());
        setError(err instanceof Error ? err.message : "brief index load failed");
        setDataSource(statusSource);
        setLoading(false);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [status, statusError, statusLoading, statusSource]);

  return { index, error, loading: loading || statusLoading, dataSource };
}
