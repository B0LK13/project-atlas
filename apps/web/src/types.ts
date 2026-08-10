export type HealthState = "healthy" | "degraded" | "unhealthy" | "unknown";

export interface ProjectSummary {
  project_id: string;
  has_project_note: boolean;
  path: string;
}

export interface VaultHealthView {
  available: boolean;
  rollup: HealthState;
  truth_plane: string;
  authority_plane: string;
  note: string;
  source: string;
  disclaimer: string;
}

export interface ReadStatus {
  vault_present: boolean;
  vault_id: string | null;
  read_plane: "unread" | "ops_snapshot" | "stub";
  health: VaultHealthView;
  projects: ProjectSummary[];
  ui_canonical: boolean;
  graph_authority: boolean;
  unknown_equals_healthy: boolean;
  /** AS-2.1 deepen: live vs isolated demo stub vs fixture sample */
  data_source?: DataSource;
  demo_isolated?: boolean;
  fixture_isolated?: boolean;
}

/** LIVE_API preferred; DEMO stub isolated; FIXTURE sample for gates. */
export type DataSource = "live_api" | "demo_stub" | "fixture";
