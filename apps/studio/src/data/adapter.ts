import type { MissionControlProjection, StudioEnvelope } from "../types";
export { unavailableEnvelope } from "./unavailable";

export const BRIDGE_URL =
  import.meta.env.VITE_ATLAS_STUDIO_BRIDGE_URL ?? "http://127.0.0.1:47631/v1/mission-control";

const REQUIRED_HONESTY = [
  "studio_ui_ne_authority",
  "ui_state_is_projection",
  "grants_no_mutation",
  "no_cli_text_parsing_as_protocol",
  "attention_ne_authorization",
  "stale_ne_current",
  "unknown_ne_healthy",
  "nested_honesty_fail_closed",
] as const;

export class ProjectionContractError extends Error {}

export function assertHonestProjection(value: unknown): asserts value is MissionControlProjection {
  if (!value || typeof value !== "object") {
    throw new ProjectionContractError("Projection payload is not an object");
  }
  const packet = value as Partial<MissionControlProjection>;
  if (packet.schema !== "ATLAS_STUDIO_MISSION_CONTROL_V1") {
    throw new ProjectionContractError("Unsupported or missing projection schema");
  }
  if (!packet.honesty || REQUIRED_HONESTY.some((key) => packet.honesty?.[key] !== true)) {
    throw new ProjectionContractError("Projection honesty contract failed closed");
  }
  if (!packet.freshness || !["LIVE", "STALE", "OFFLINE", "UNKNOWN"].includes(packet.freshness.state)) {
    throw new ProjectionContractError("Projection freshness is missing or invalid");
  }
  if (!packet.views || !Array.isArray(packet.attention)) {
    throw new ProjectionContractError("Projection views are incomplete");
  }
  if (typeof packet.repository !== "string" || typeof packet.generated_at_utc !== "string"
      || typeof packet.snapshot_fingerprint !== "string"
      || !packet.provenance || typeof packet.provenance.generator !== "string"
      || packet.provenance.presentation_only !== true
      || !["HEALTHY", "DEGRADED", "UNKNOWN", "STALE", "OFFLINE", "BLOCKED", "HUMAN_ATTENTION_REQUIRED"].includes(packet.mission_status ?? "")) {
    throw new ProjectionContractError("Projection identity or provenance is invalid");
  }
  for (const view of Object.values(packet.views)) {
    if (!view || typeof view !== "object" || !Array.isArray(view.notes)
        || view.notes.some(note => typeof note !== "string")
        || !["OK", "DEGRADED", "UNKNOWN", "BLOCKED", "STALE", "OFFLINE"].includes(view.status)
        || (view.summary != null && (typeof view.summary !== "object" || Array.isArray(view.summary)))) {
      throw new ProjectionContractError("Malformed projection view");
    }
  }
  for (const item of packet.attention) {
    if (!item || typeof item.attention_id !== "string" || typeof item.title !== "string"
        || typeof item.kind !== "string" || typeof item.tier !== "number"
        || (item.detail != null && typeof item.detail !== "string")
        || item.attention_ne_authorization !== true
        || ["authorized", "permitted", "executable", "authorization_granted", "mutation_authorized"]
          .some(key => (item as unknown as Record<string, unknown>)[key] === true)) {
      throw new ProjectionContractError("Malformed or authority-bearing attention");
    }
  }
  if (packet.mission_status === "HEALTHY" && (packet.freshness.state !== "LIVE"
      || Object.values(packet.views).some(view => view.status === "UNKNOWN"))) {
    throw new ProjectionContractError("Unknown or stale projection cannot be healthy");
  }
}

export function envelopeFromProjection(packet: MissionControlProjection): StudioEnvelope {
  const current = packet.freshness.state === "LIVE";
  return {
    source: {
      kind: "PROJECTION",
      label: current ? "CURRENT READ-ONLY PROJECTION" : `${packet.freshness.state} READ-ONLY PROJECTION`,
      detail: current
        ? "Rebuilt from the Atlas A1 typed projection. This view grants no authority."
        : "Projection data is not current; UNKNOWN and STALE are never promoted to healthy.",
      current,
    },
    projection: packet,
  };
}

export async function loadProjection(signal?: AbortSignal): Promise<StudioEnvelope> {
  const response = await fetch(BRIDGE_URL, {
    method: "GET",
    headers: { Accept: "application/json" },
    cache: "no-store",
    signal,
  });
  if (!response.ok) {
    throw new ProjectionContractError(`Bridge returned ${response.status}`);
  }
  const packet: unknown = await response.json();
  assertHonestProjection(packet);
  return envelopeFromProjection(packet);
}
