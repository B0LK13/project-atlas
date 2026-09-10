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

export type HonestyBlock = Record<string, true>;

export interface NestedOperationalProjection {
  schema: string;
  honesty: HonestyBlock;
  [key: string]: unknown;
}

export interface ControlViewProjection extends NestedOperationalProjection {
  schema: "ATLAS_GLOBAL_CONTROL_VIEW_V1";
  view_fingerprint: string;
  panels: Record<string, Record<string, unknown>>;
}

export interface TelemetryProjection extends NestedOperationalProjection {
  schema: "ATLAS_COORDINATION_TELEMETRY_V1";
  truth_fingerprint: string;
  telemetry_fingerprint: string;
  categories: Record<string, Record<string, unknown>>;
}

export interface EfficiencyMetricsProjection extends NestedOperationalProjection {
  schema: "ATLAS_EFFICIENCY_METRICS_V1";
  source_telemetry_fingerprint: string;
  summary: Record<string, number | null>;
}

export interface StudioPanel<TBody = Record<string, unknown>> {
  status: "OK" | "DEGRADED" | "UNKNOWN";
  notes: string[];
  body?: TBody | null;
}

export interface StudioObservationEvent {
  schema: "ATLAS_STUDIO_EVENT_V1";
  event_id: string;
  timestamp_utc: string;
  kind: "OBSERVATION" | "SLICE_STATUS" | "PANEL_STATUS";
  honesty: HonestyBlock;
  payload: Record<string, unknown>;
  panel?: string | null;
  message?: string;
  [key: string]: unknown;
}

export interface StudioSnapshot {
  schema: "ATLAS_STUDIO_SNAPSHOT_V1";
  generated_at_utc: string;
  repository: string;
  agent?: string | null;
  agent_status?: string;
  slice_status: "OK" | "DEGRADED" | "UNKNOWN";
  snapshot_fingerprint: string;
  honesty: HonestyBlock;
  panels: {
    control_view: StudioPanel<ControlViewProjection>;
    telemetry: StudioPanel<TelemetryProjection>;
    efficiency_metrics: StudioPanel<EfficiencyMetricsProjection>;
    residuals: StudioPanel<Record<string, unknown>>;
  };
  observation_events?: StudioObservationEvent[];
  provenance: {
    generator: string;
    presentation_only: true;
    truth_sources?: string[];
    notes?: string[];
    [key: string]: unknown;
  };
  [key: string]: unknown;
}

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
  [key: string]: unknown;
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
  honesty: HonestyBlock;
  views: Record<string, MissionControlView>;
  attention: AttentionItem[];
  // Fixture/unavailable envelopes intentionally carry non-operational placeholders.
  // The adapter narrows live packets to StudioSnapshot after schema validation.
  studio_snapshot: StudioSnapshot | Record<string, unknown>;
  observation_events?: StudioObservationEvent[];
  provenance: {
    generator: string;
    presentation_only: true;
    truth_sources?: string[];
    notes?: string[];
    [key: string]: unknown;
  };
}

export interface MissionJourneyProjection {
  schema: "ATLAS_STUDIO_MISSION_JOURNEY_V1";
  generated_at_utc: string;
  repository: string | null;
  agent?: string | null;
  mission: Record<string, unknown>;
  knowledge: { state: string; items: Array<Record<string, unknown>>; notes?: string[] };
  development: Record<string, unknown>;
  next_actions: Record<string, unknown>;
  honesty: HonestyBlock;
  provenance: Record<string, unknown>;
}

export interface TaskContextProjection {
  schema: "ATLAS_STUDIO_TASK_CONTEXT_V1";
  generated_at_utc: string;
  repository?: string | null;
  agent?: string | null;
  lane: string;
  freshness: Record<string, unknown>;
  lane_state: Record<string, unknown>;
  knowledge: Record<string, unknown>;
  next_step: Record<string, unknown>;
  recovery: Array<Record<string, unknown>>;
  continuation: Record<string, unknown>;
  missing: string[];
  honesty: HonestyBlock;
  provenance: Record<string, unknown>;
  fingerprint: string;
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
    localFreshness?: {
      state: FreshnessState;
      ageSeconds: number | null;
      checkedAtUtc: string;
      label: "LOCAL AGE CHECK";
    };
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
