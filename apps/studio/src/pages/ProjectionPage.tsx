import type { ReactNode } from "react";
import type { ScreenId, StudioEnvelope } from "../types";
import type { MissionJourneyProjection, TaskContextProjection } from "../types";
import { Panel } from "../components/Panel";
import { MissionJourneyPanel } from "./MissionJourneyPanel";

const views: Partial<Record<ScreenId, string[]>> = {
  agents: ["agents_lanes", "ownership"], "work-graph": ["frontier", "ownership"],
  repository: ["stacks"], verification: ["ci_iv", "human_gates", "evidence", "postmerge_seal"],
  knowledge: [], chronicle: ["telemetry"], projects: ["health", "residuals"],
};
const label = (value: string) => value.replaceAll("_", " ");

// A1 summaries are source values, never inferred activity or permission.
function Value({ value }: { value: unknown }): ReactNode {
  if (value == null) return <span className="projection-unknown">Unavailable</span>;
  if (Array.isArray(value)) return value.length
    ? <ul className="source-value-list">{value.map((item, i) => <li key={i}><Value value={item} /></li>)}</ul>
    : <span>No entries supplied</span>;
  if (typeof value === "object") return <dl className="projection-fields">{Object.entries(value).map(([key, item]) =>
    <div key={key}><dt>{label(key)}</dt><dd><Value value={item} /></dd></div>)}</dl>;
  return String(value);
}

export function ProjectionPage({ data, screen, journey, journeyLoading, journeyError, taskContext, taskLoading, taskError, onLoadTask }: { data: StudioEnvelope; screen: ScreenId; journey?: MissionJourneyProjection | null; journeyLoading?: boolean; journeyError?: string | null; taskContext?: TaskContextProjection | null; taskLoading?: boolean; taskError?: string | null; onLoadTask?: (lane: string) => void }) {
  const packet = data.projection;
  const mission = screen === "mission-control";
  const keys = mission ? Object.keys(packet.views) : views[screen] ?? [];
  const metric = (view: string, key: string) => <Value value={packet.views[view]?.summary?.[key]} />;
  const attention = (items: typeof packet.attention) => items.map(item => <article className="projection-attention" key={item.attention_id}>
    <h3>{item.title}</h3><p>{item.detail}</p>
    <details><summary>Source classification</summary><p>{item.kind} · tier {item.tier} · {item.attention_id}</p></details>
  </article>);
  return <div className="screen projection-screen">
    <header className="screen-header"><div><p>Atlas / Engineering workstation</p>
      <h1>{mission ? "Mission Control" : label(screen.replaceAll("-", " "))}</h1>
      <span>{packet.repository || "Project identity unavailable"}</span></div>
      <strong>{data.source.localFreshness?.state ?? packet.freshness.state} · Source status: {packet.mission_status}</strong>
    </header>
    {data.source.kind === "UNAVAILABLE" ? <Panel eyebrow={data.source.label} title={data.source.label === "LOADING PROJECTION" ? "Loading projection" : "Projection unavailable"}>
      <p>{data.source.detail}</p><p>No operational state is available. Refresh to retry, or inspect the explicit design preview in Environment.</p>
    </Panel> : <>
      {mission && <section className="mission-orientation" aria-label="Mission context">
        <div><span className="context-label">Current objective</span><h2>Mission objective unavailable</h2>
          <p>A1 supplies repository coordination state, but no declared mission objective. Studio will not infer one.</p></div>
        <div className="mission-boundary"><strong>Read, inspect, understand.</strong><span>Attention is not authorization.<br />Studio grants no mutation.</span></div>
      </section>}
      <div className={mission ? "live-overview" : ""}>
        <Panel className="attention-panel" eyebrow="ATTENTION ≠ AUTHORIZATION" title={mission ? "Next attention" : "Attention"} meta={<span>{packet.attention.length} supplied</span>}>
          {packet.attention.length ? <>{attention(packet.attention.slice(0, 3))}
            {packet.attention.length > 3 && <details className="remaining-attention"><summary>Inspect {packet.attention.length - 3} more attention items</summary>{attention(packet.attention.slice(3))}</details>}
          </> : <p>No attention items supplied by this projection. This does not establish health.</p>}
        </Panel>
        {mission && <div className="live-instruments">
          <section className="signal-instrument" aria-label="Agent activity"><header><h2>Agent activity</h2><a href="#/agents">Inspect agents</a></header>
            <div className="signal-reading"><strong>{metric("agents_lanes", "active_count")}</strong><span>active in source directory</span></div>
            <div className="agent-identities">{metric("agents_lanes", "active_agent_ids")}</div>
            <p>Directory activity does not prove a running task.</p>
          </section>
          <section className="signal-instrument" aria-label="Runnable frontier"><header><h2>Runnable frontier</h2><a href="#/work-graph">Inspect frontier</a></header>
            <div className="signal-pair"><div><strong>{metric("frontier", "eligible_count")}</strong><span>eligible</span></div><div><strong>{metric("frontier", "blocked_count")}</strong><span>blocked</span></div></div>
            <p>Source status: {packet.views.frontier?.status ?? "UNKNOWN"}. Eligibility is not permission to execute.</p>
          </section>
          <section className="signal-instrument" aria-label="Verification posture"><header><h2>Verification posture</h2><a href="#/verification">Inspect verification</a></header>
            <div className="signal-pair"><div><strong>{metric("ci_iv", "waiting_ci")}</strong><span>waiting on CI</span></div><div><strong>{metric("ci_iv", "waiting_iv")}</strong><span>waiting on IV</span></div></div>
            <p>Evidence: {packet.views.evidence?.status ?? "UNKNOWN"} · Seal: {packet.views.postmerge_seal?.status ?? "UNKNOWN"}. CI ≠ IV ≠ merge.</p>
          </section>
        </div>}
      </div>
      {mission && <h2 className="source-section-title">Source detail</h2>}
      <div className="projection-grid">{keys.map(key => {
        const view = packet.views[key];
        return <Panel key={key} eyebrow={view?.status ?? "UNKNOWN"} title={label(key)}>
          {view ? <>
            {view.summary && Object.keys(view.summary).length ? <dl className="projection-fields">
              {Object.entries(view.summary).map(([field, value]) => <div key={field}><dt>{label(field)}</dt><dd><Value value={value} /></dd></div>)}
            </dl> : <p>Summary unavailable.</p>}
            {view.notes.length > 0 && <details className="projection-notes"><summary>Source notes</summary>{view.notes.map((note, index) => <p key={index}>{note}</p>)}</details>}
          </> : <p>This view is unavailable in the supplied contract.</p>}
        </Panel>;
      })}</div>
      {!keys.length && <Panel eyebrow="NOT WIRED" title="Detail projection unavailable"><p>A1 does not supply this detail view. Demonstration content is available only in explicitly selected fixture mode.</p></Panel>}
      {mission && onLoadTask && <MissionJourneyPanel journey={journey ?? null} loading={journeyLoading ?? false} error={journeyError ?? null} taskContext={taskContext ?? null} taskLoading={taskLoading ?? false} taskError={taskError ?? null} onLoadTask={onLoadTask} />}
      <details><summary>Projection provenance</summary><dl className="projection-fields">
        <div><dt>Generated at (source supplied)</dt><dd>{packet.generated_at_utc}</dd></div>
        <div><dt>Fingerprint</dt><dd>{packet.snapshot_fingerprint}</dd></div>
        <div><dt>Generator</dt><dd>{packet.provenance.generator}</dd></div>
      </dl></details>
    </>}
  </div>;
}
