export type ViewStatus =
  | "OK"
  | "DEGRADED"
  | "UNKNOWN"
  | "BLOCKED"
  | "STALE"
  | "OFFLINE";

export type FreshnessState = "LIVE" | "STALE" | "OFFLINE" | "UNKNOWN";

export type TruthState =
  | "OBSERVED"
  | "DERIVED"
  | "INFERRED"
  | "SIMULATED"
  | "UNKNOWN"
  | "CONTESTED"
  | "STALE";

export type WorkflowState =
  | "RUNNING"
  | "READY"
  | "BLOCKED"
  | "OWNER_REQUIRED"
  | "WAITING_FOR_CI"
  | "WAITING_FOR_IV"
  | "VERIFIED"
  | "FAILED"
  | "MERGED"
  | "SEALED"
  | "UNKNOWN";

export interface MissionControlView {
  status: ViewStatus;
  notes: string[];
  summary?: Record<string, unknown> | null;
  source_panel?: string | null;
  references?: Array<Record<string, unknown>>;
  [key: string]: unknown;
}

export interface AttentionItem {
  attention_id: string;
  kind: string;
  tier: number;
  title: string;
  detail?: string;
  attention_ne_authorization: true;
  references?: Array<Record<string, unknown>>;
}

export interface MissionControlProjection {
  schema: "ATLAS_STUDIO_MISSION_CONTROL_V1";
  generated_at_utc: string;
  repository: string;
  agent?: string | null;
  agent_status: string;
  slice_status: "OK" | "DEGRADED" | "UNKNOWN";
  mission_status:
    | "HEALTHY"
    | "DEGRADED"
    | "UNKNOWN"
    | "STALE"
    | "OFFLINE"
    | "BLOCKED"
    | "HUMAN_ATTENTION_REQUIRED";
  snapshot_fingerprint: string;
  freshness: {
    generated_at_utc: string;
    snapshot_fingerprint: string;
    max_age_seconds: number;
    age_seconds?: number | null;
    state: FreshnessState;
    notes?: string[];
  };
  honesty: Record<string, boolean>;
  views: Record<string, MissionControlView>;
  attention: AttentionItem[];
  studio_snapshot: Record<string, unknown>;
  observation_events?: Array<Record<string, unknown>>;
  provenance: {
    generator: string;
    presentation_only: true;
    truth_sources?: string[];
    notes?: string[];
    [key: string]: unknown;
  };
}

export type AgentPresence = "ACTIVE" | "IDLE" | "WAITING" | "INACTIVE";

export interface AgentPreview {
  id: string;
  name: string;
  role: string;
  model: string;
  platform: string;
  presence: AgentPresence;
  workflow: WorkflowState;
  exists: boolean;
  authorized: boolean;
  ownsLane: boolean;
  lane: string | null;
  elapsed: string;
  evidence: string;
  blocker?: string;
}

export interface WorkNodePreview {
  id: string;
  label: string;
  eyebrow: string;
  state: string;
  truth: TruthState;
  x: number;
  y: number;
  current?: boolean;
  owner?: string | null;
  detail: string;
}

export interface WorkEdgePreview {
  from: string;
  to: string;
  state: "complete" | "active" | "blocked" | "future";
}

export interface VerificationStagePreview {
  id: string;
  label: string;
  state: WorkflowState;
  truth: TruthState;
  detail: string;
}

export interface KnowledgePreview {
  id: string;
  title: string;
  summary: string;
  truth: TruthState;
  source: string;
  age: string;
  conflict?: string;
}

export interface ChroniclePreview {
  id: string;
  time: string;
  kind: string;
  title: string;
  detail: string;
  truth: TruthState;
  actor: string;
}

export interface RepositoryFilePreview {
  path: string;
  state: "added" | "modified" | "deleted";
  additions: number;
  deletions: number;
}

export interface StudioPreviewCatalog {
  label: "DESIGN_PREVIEW";
  objective: string;
  objectiveDetail: string;
  agents: AgentPreview[];
  nodes: WorkNodePreview[];
  edges: WorkEdgePreview[];
  verification: VerificationStagePreview[];
  knowledge: KnowledgePreview[];
  chronicle: ChroniclePreview[];
  repository: {
    branch: string;
    head: string;
    tree: string;
    base: string;
    baseTree: string;
    state: "CLEAN" | "CHANGED" | "UNKNOWN";
    pullRequest: string;
    files: RepositoryFilePreview[];
  };
}

export type DataSourceKind = "PROJECTION" | "DESIGN_PREVIEW" | "UNAVAILABLE";

export interface StudioEnvelope {
  source: {
    kind: DataSourceKind;
    label: string;
    detail: string;
    current: boolean;
  };
  projection: MissionControlProjection;
  preview?: StudioPreviewCatalog;
}

export type ScreenId =
  | "mission-control"
  | "projects"
  | "agents"
  | "work-graph"
  | "repository"
  | "verification"
  | "knowledge"
  | "chronicle"
  | "settings"
  | "design-lab";

export type ThemeMode = "dark" | "light";
export type DensityMode = "comfortable" | "compact" | "focus";
