import { describe, expect, it } from "vitest";
import { assertHonestProjection, envelopeFromProjection, unavailableEnvelope, ProjectionContractError } from "./adapter";
import { fixtureEnvelope } from "./fixture";
import type { MissionControlProjection } from "../types";

function projection(overrides: Partial<MissionControlProjection> = {}): MissionControlProjection {
  return {
    ...fixtureEnvelope.projection,
    freshness: { ...fixtureEnvelope.projection.freshness, state: "LIVE" },
    ...overrides,
  };
}

describe("Studio projection boundary", () => {
  it("accepts the typed A1 honesty contract", () => {
    expect(() => assertHonestProjection(projection())).not.toThrow();
  });

  it("fails closed when any required honesty invariant is absent", () => {
    const packet = projection({
      honesty: { ...fixtureEnvelope.projection.honesty, grants_no_mutation: false },
    });
    expect(() => assertHonestProjection(packet)).toThrow(ProjectionContractError);
  });

  it.each(["STALE", "OFFLINE", "UNKNOWN"] as const)("never labels %s projection current", (state) => {
    const envelope = envelopeFromProjection(
      projection({ freshness: { ...fixtureEnvelope.projection.freshness, state } }),
    );
    expect(envelope.source.current).toBe(false);
    expect(envelope.source.label).toContain(state);
    expect(envelope.source.detail).toContain("never promoted to healthy");
  });

  it("keeps unavailable live data visibly isolated from design fixtures", () => {
    const envelope = unavailableEnvelope("Bridge returned 503");
    expect(envelope.source.kind).toBe("UNAVAILABLE");
    expect(envelope.source.current).toBe(false);
    expect(envelope.preview).toBeUndefined();
    expect(envelope.source.detail).toContain("Bridge returned 503");
  });
});
