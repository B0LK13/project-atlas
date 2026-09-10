import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ProjectionPage } from "./ProjectionPage";
import { fixtureEnvelope } from "../data/fixture";
import { assertHonestProjection, envelopeFromProjection, unavailableEnvelope } from "../data/adapter";

describe("read-only rendering boundary", () => {
  it("keeps unavailable separate from fixtures", () => {
    const data = unavailableEnvelope("Bridge returned 503");
    expect(data.preview).toBeUndefined();
    expect(data.source.current).toBe(false);
    const html = renderToStaticMarkup(<ProjectionPage data={data} screen="agents" />);
    expect(html).toContain("Projection unavailable");
    expect(html).not.toContain("0 active");
    expect(html).not.toContain("HEALTHY");
  });
  it("renders supplied values and escapes untrusted content", () => {
    const packet = structuredClone(fixtureEnvelope.projection);
    packet.views.agents_lanes = {status: "DEGRADED", notes: [], summary: {active_agent_ids: ["<script>alert(1)</script>"]}};
    const render = () => renderToStaticMarkup(<ProjectionPage data={envelopeFromProjection(packet)} screen="agents" />);
    expect(render()).toContain("&lt;script&gt;");
    expect(render()).not.toContain("<script>");
    packet.views.agents_lanes.summary = {active_agent_ids: ["controlled-agent-change"]};
    expect(render()).toContain("controlled-agent-change");
    expect(render()).not.toContain("alert(1)");
  });
  it("rejects malformed render fields", () => {
    const packet = structuredClone(fixtureEnvelope.projection);
    packet.views.agents_lanes = {status: "UNKNOWN", notes: [42 as unknown as string]};
    expect(() => assertHonestProjection(packet)).toThrow("Malformed projection view");
  });
});


describe("Mission Control hierarchy", () => {
  it("shows supported activity and verification beside explicit missing objective", () => {
    const packet = structuredClone(fixtureEnvelope.projection);
    packet.views.agents_lanes = {status:"OK", notes:[], summary:{active_count:3, active_agent_ids:["agent-from-source"]}};
    packet.views.ci_iv = {status:"OK", notes:[], summary:{waiting_ci:4, waiting_iv:9}};
    const html = renderToStaticMarkup(<ProjectionPage data={envelopeFromProjection(packet)} screen="mission-control" />);
    expect(html).toContain("Mission objective unavailable");
    expect(html).toContain("Agent activity");
    expect(html).toContain("agent-from-source");
    expect(html).toContain("Verification posture");
    expect(html).toContain("Runnable frontier");
    expect(html).toContain("Next attention");
    expect(html).not.toContain("<pre>");
  });
});
