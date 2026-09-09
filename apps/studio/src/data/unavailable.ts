import type { StudioEnvelope } from "../types";

// Local absence state, never a fabricated Atlas observation or fixture.
export function unavailableEnvelope(reason: string): StudioEnvelope {
  return {
    source: { kind: "UNAVAILABLE", label: "PROJECTION UNAVAILABLE", detail: reason, current: false },
    projection: {
      schema: "ATLAS_STUDIO_MISSION_CONTROL_V1", repository: "", generated_at_utc: "",
      agent_status: "UNKNOWN", slice_status: "UNKNOWN", mission_status: "UNKNOWN",
      snapshot_fingerprint: "", freshness: { state: "UNKNOWN", generated_at_utc: "",
        snapshot_fingerprint: "", max_age_seconds: 0 },
      honesty: {}, views: {}, attention: [], studio_snapshot: {},
      provenance: { generator: "Studio local absence state", presentation_only: true },
    },
  };
}
