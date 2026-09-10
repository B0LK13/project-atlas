import type { ValidateFunction } from "ajv";
import {
  validateMissionControl, validateStudioSnapshot, validateStudioEvent,
  validateControlView, validateTelemetry, validateEfficiencyMetrics,
} from "virtual:atlas-projection-validators";
import type {
  FreshnessState,
  MissionControlProjection,
  StudioEnvelope,
  StudioSnapshot,
} from "../types";
export { unavailableEnvelope } from "./unavailable";

export const BRIDGE_URL =
  import.meta.env.VITE_ATLAS_STUDIO_BRIDGE_URL ?? "http://127.0.0.1:47631/v1/mission-control";

const ATTENTION_AUTHORITY_KEYS = [
  "authorized",
  "permitted",
  "executable",
  "authorization_granted",
  "mutation_authorized",
] as const;

export class ProjectionContractError extends Error {}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function validationMessage(label: string, validate: ValidateFunction): string {
  const details = (validate.errors ?? [])
    .slice(0, 5)
    .map((error) => `${error.instancePath || "<root>"} ${error.message ?? "is invalid"}`)
    .join("; ");
  return `${label} contract failed: ${details}`;
}

function assertSchema(label: string, validate: ValidateFunction, value: unknown): void {
  if (validate(value)) return;
  const message = validationMessage(label, validate);
  if (label === "A1" && validate.errors?.some((error) => error.instancePath.startsWith("/views/"))) {
    throw new ProjectionContractError(`Malformed projection view: ${message}`);
  }
  throw new ProjectionContractError(message);
}

function assertHonesty(label: string, value: unknown): void {
  if (!isRecord(value) || Object.values(value).some((flag) => flag !== true)) {
    throw new ProjectionContractError(`${label} honesty contract failed closed`);
  }
}

function assertNestedBody(
  label: string,
  value: unknown,
  schema: string,
  validate: ValidateFunction,
): void {
  if (!isRecord(value) || value.schema !== schema) {
    throw new ProjectionContractError(`${label} uses an unsupported or malformed schema`);
  }
  assertSchema(label, validate, value);
  assertHonesty(label, value.honesty);
}

function parseUtcMillis(value: string): number | null {
  const raw = value.trim();
  if (!raw) return null;
  const normalized = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?$/.test(raw)
    ? `${raw}Z`
    : raw;
  const parsed = Date.parse(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function assertEmbeddedSnapshot(packet: MissionControlProjection): void {
  const snapshot = packet.studio_snapshot as StudioSnapshot;
  assertSchema("embedded A0 snapshot", validateStudioSnapshot, snapshot);
  assertHonesty("embedded A0 snapshot", snapshot.honesty);

  const { control_view: controlView, telemetry, efficiency_metrics: metrics } = snapshot.panels;
  if (controlView.body != null) {
    assertNestedBody(
      "embedded A0 control_view",
      controlView.body,
      "ATLAS_GLOBAL_CONTROL_VIEW_V1",
      validateControlView,
    );
  }
  if (telemetry.body != null) {
    assertNestedBody(
      "embedded A0 telemetry",
      telemetry.body,
      "ATLAS_COORDINATION_TELEMETRY_V1",
      validateTelemetry,
    );
  }
  if (metrics.body != null) {
    assertNestedBody(
      "embedded A0 efficiency_metrics",
      metrics.body,
      "ATLAS_EFFICIENCY_METRICS_V1",
      validateEfficiencyMetrics,
    );
  }

  for (const event of snapshot.observation_events ?? []) {
    assertSchema("embedded A0 observation event", validateStudioEvent, event);
    assertHonesty("embedded A0 observation event", event.honesty);
  }

  if (snapshot.slice_status === "OK") {
    for (const [name, panel] of Object.entries(snapshot.panels)) {
      if (panel.status === "DEGRADED" || panel.status === "UNKNOWN") {
        throw new ProjectionContractError(
          `embedded A0 slice_status cannot be OK while panels/${name}/status=${panel.status}`,
        );
      }
    }
  }
}

export function assertHonestProjection(value: unknown): asserts value is MissionControlProjection {
  assertSchema("A1", validateMissionControl, value);
  const packet = value as MissionControlProjection;
  assertHonesty("A1", packet.honesty);
  assertEmbeddedSnapshot(packet);

  for (const event of packet.observation_events ?? []) {
    assertSchema("A1 observation event", validateStudioEvent, event);
    assertHonesty("A1 observation event", event.honesty);
  }
  for (const [index, item] of packet.attention.entries()) {
    if (ATTENTION_AUTHORITY_KEYS.some((key) => item[key] === true)) {
      throw new ProjectionContractError(`A1 attention/${index} carries forbidden authority`);
    }
  }

  if (packet.freshness.state === "LIVE" && parseUtcMillis(packet.freshness.generated_at_utc) === null) {
    throw new ProjectionContractError("A1 LIVE freshness timestamp is invalid");
  }
  if (packet.mission_status === "HEALTHY") {
    if (packet.freshness.state !== "LIVE") {
      throw new ProjectionContractError("A1 mission_status HEALTHY requires freshness.state=LIVE");
    }
    for (const name of ["postmerge_seal", "evidence"] as const) {
      if (packet.views[name].status === "UNKNOWN") {
        throw new ProjectionContractError(
          `A1 mission_status cannot be HEALTHY while views/${name}=UNKNOWN`,
        );
      }
    }
    if (packet.views.frontier.notes.includes("AGENT_MATRIX_MISMATCH")) {
      throw new ProjectionContractError("A1 mission_status cannot be HEALTHY under AGENT_MATRIX_MISMATCH");
    }
  }
}

function localFreshness(
  packet: MissionControlProjection,
  localNowMs: number,
): NonNullable<StudioEnvelope["source"]["localFreshness"]> {
  const generatedMs = parseUtcMillis(packet.freshness.generated_at_utc);
  const ageSeconds = generatedMs === null || generatedMs > localNowMs
    ? null
    : Math.round(Math.max(0, (localNowMs - generatedMs) / 1_000) * 1_000) / 1_000;
  let state: FreshnessState = packet.freshness.state;
  if (state === "LIVE" && (ageSeconds === null || ageSeconds > packet.freshness.max_age_seconds)) {
    state = ageSeconds === null ? "UNKNOWN" : "STALE";
  }
  return {
    state,
    ageSeconds,
    checkedAtUtc: new Date(localNowMs).toISOString(),
    label: "LOCAL AGE CHECK",
  };
}

export function envelopeFromProjection(
  packet: MissionControlProjection,
  localNowMs = Date.now(),
): StudioEnvelope {
  const local = localFreshness(packet, localNowMs);
  const current = packet.freshness.state === "LIVE" && local.state === "LIVE";
  const effectiveState = current ? "CURRENT" : local.state;
  return {
    source: {
      kind: "PROJECTION",
      label: `${effectiveState} READ-ONLY PROJECTION · LOCAL AGE CHECK`,
      detail: current
        ? `Source generated ${packet.freshness.generated_at_utc}; local age ${local.ageSeconds ?? "unknown"}s. This view grants no authority.`
        : "Projection data is not current; UNKNOWN and STALE are never promoted to healthy. Age is checked locally from the source-supplied timestamp.",
      current,
      localFreshness: local,
    },
    projection: packet,
  };
}

export async function loadProjection(
  signal?: AbortSignal,
  localNowMs?: number,
): Promise<StudioEnvelope> {
  const response = await fetch(BRIDGE_URL, {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    const explanations: Record<string, string> = {
      PROJECTION_FAILED_AUTHENTICATION: "GitHub authentication unavailable. Check gh auth status outside Studio, then refresh.",
      PROJECTION_FAILED_UPSTREAM_READS: "GitHub reads failed. Check network access and bridge timing diagnostics, then refresh.",
      PROJECTION_FAILED_PROJECTION_CONSTRUCTION: "A1 projection construction failed. Inspect bridge diagnostics before retrying.",
      PROJECTION_DEADLINE: "The read-only projection exceeded its 20 second budget. Check bridge timing diagnostics, then refresh.",
      A1_SCHEMA_VALIDATION_FAILED: "A1 returned an unsupported contract. Update the matching bridge and Studio versions.",
      BUSY: "The bridge is already serving its request limit. Wait for those reads to finish, then refresh.",
    };
    let reason: unknown;
    try {
      const body = await response.json();
      reason = body?.reason ?? body?.status;
    } catch { /* An absent diagnostic is not a successful projection. */ }
    throw new ProjectionContractError(typeof reason === "string" && Object.hasOwn(explanations, reason)
      ? explanations[reason] : `Bridge returned ${response.status}`);
  }
  const packet: unknown = await response.json();
  assertHonestProjection(packet);
  return envelopeFromProjection(packet, localNowMs ?? Date.now());
}
