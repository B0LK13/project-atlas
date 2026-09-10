import type { ReactNode } from "react";
import type { ScreenId, StudioEnvelope } from "../types";
import type { MissionJourneyProjection, TaskContextProjection } from "../types";
import { Panel } from "../components/Panel";
import { MissionJourneyPanel } from "./MissionJourneyPanel";
import { attentionGroupLabel, attentionLabel, freshnessLabel, groupAttention, metricLabel, sourceStateLabel } from "./missionControlModel";
import { pagePurpose, secondaryAttentionLabel, viewLabel } from "./pagePurpose";
import { useEffect, useMemo, useState } from "react";

const views: Partial<Record<ScreenId, string[]>> = {
  agents: ["agents_lanes", "ownership"], "work-graph": ["frontier", "ownership"],
  repository: ["stacks"], verification: ["ci_iv", "human_gates", "evidence", "postmerge_seal"],
  knowledge: [], chronicle: ["telemetry"], projects: ["health", "residuals"],
};
const label = (value: string) => value.replaceAll("_", " ");
const selectionStorageKey = "atlas.selectedAttention";

function readStoredSelection(repository: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(selectionStorageKey);
    if (!raw) return null;
    const stored: unknown = JSON.parse(raw);
    if (stored && typeof stored === "object" && "attentionId" in stored && "repository" in stored
      && typeof stored.attentionId === "string" && typeof stored.repository === "string"
      && stored.repository === repository) return stored.attentionId;
    window.localStorage.removeItem(selectionStorageKey);
  } catch { /* presentation state is optional and may be unavailable */ }
  return null;
}

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
  const purpose = pagePurpose(screen);
  const keys = mission ? Object.keys(packet.views) : views[screen] ?? [];
  const metric = (view: string, key: string) => <Value value={packet.views[view]?.summary?.[key]} />;
  const attentionGroups = useMemo(() => groupAttention(packet.attention), [packet.attention]);
  const [selectedAttentionId, setSelectedAttentionId] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    return readStoredSelection(data.projection.repository);
  });
  const [selectionNotice, setSelectionNotice] = useState<string | null>(null);
  const selectedAttention = packet.attention.find((item) => item.attention_id === selectedAttentionId) ?? null;
  useEffect(() => {
    // Source order is the only supported initial ordering. Selecting the first
    // record makes the bounded queue useful without implying priority.
    if (mission && !selectedAttentionId && attentionGroups[0]?.items[0]) {
      selectAttention(attentionGroups[0].items[0].attention_id);
    }
  }, [attentionGroups, mission, selectedAttentionId]);
  const selectAttention = (id: string) => {
    setSelectedAttentionId(id);
    try { window.localStorage.setItem(selectionStorageKey, JSON.stringify({ attentionId: id, repository: packet.repository })); } catch { /* storage is optional */ }
  };
  useEffect(() => {
    // Refresh temporarily swaps in an unavailable envelope; preserve selection
    // through that transport state and only clear it against a real projection.
    if (data.source.kind !== "PROJECTION") return;
    if (selectedAttentionId && !packet.attention.some((item) => item.attention_id === selectedAttentionId)) {
      setSelectionNotice(`The selected attention item (${selectedAttentionId}) is no longer in this projection.`);
      setSelectedAttentionId(null);
      try { window.localStorage.removeItem(selectionStorageKey); } catch { /* storage is optional */ }
    }
  }, [data.source.kind, packet.attention, selectedAttentionId]);
  const inspectHref = (item: (typeof packet.attention)[number]) => {
    const ref = item.references?.[0];
    if (ref?.kind === "view") {
      const route = String(ref.id);
      return ["agents_lanes", "ownership"].includes(route) ? "#/agents" : route === "frontier" ? "#/work-graph" : route === "ci_iv" || route === "evidence" || route === "human_gates" ? "#/verification" : "#/mission-control";
    }
    if (ref?.kind === "action_id" || item.kind === "BLOCKED_HIGH_VALUE" || item.kind === "HUMAN_GATE") return "#/work-graph";
    if (item.kind === "EXTERNAL_IV_GATED") return "#/verification";
    return "#/mission-control";
  };
  const renderAttentionDetail = (item: (typeof packet.attention)[number]) => {
    const translated = attentionLabel(item);
    return <div className="attention-detail-content"><p className="attention-detail-primary">{translated.primary}</p><p>{item.detail ?? "No detail supplied by the source."}</p><details><summary>Source record</summary><dl className="projection-fields"><div><dt>Exact cause</dt><dd>{translated.exact}</dd></div><div><dt>Record</dt><dd>{item.attention_id}</dd></div><div><dt>Source tier</dt><dd>{item.tier}</dd></div><div><dt>References</dt><dd><Value value={item.references ?? []} /></dd></div></dl></details><a className="attention-inspect-link" href={inspectHref(item)}>Inspect supported detail</a></div>;
  };
  return <div className="screen projection-screen">
    <header className="screen-header"><div><p>Atlas / Engineering workstation</p>
      <h1>{mission ? "Mission Control" : label(screen.replaceAll("-", " "))}</h1>
      <span>{packet.repository || "Project identity unavailable"}</span></div>
      <strong>{data.source.localFreshness?.state ?? packet.freshness.state} · Source status: {packet.mission_status}</strong>
    </header>
    {data.source.kind === "UNAVAILABLE" ? <Panel eyebrow={data.source.label} title={data.source.label === "LOADING PROJECTION" ? "Loading projection" : "Projection unavailable"}>
      <p>{data.source.detail}</p><p>No operational state is available. Refresh to retry, or inspect the explicit design preview in Environment.</p>
    </Panel> : <>
      {!mission && <section className="page-purpose" aria-label={`${label(screen)} purpose`}><div><span className="context-label">{label(screen)} workspace</span><h2>{purpose.question}</h2><p>{purpose.intro}</p></div><a className="compact-attention-indicator" href="#/mission-control" aria-label={secondaryAttentionLabel(packet.attention.length)}>{secondaryAttentionLabel(packet.attention.length)}</a></section>}
      {!mission && selectedAttention && <section className="selected-context-strip" aria-label="Selected work context"><div><span className="context-label">Selected attention context</span><strong>{attentionLabel(selectedAttention).primary}</strong><small>{selectedAttention.attention_id} · carried from Mission Control</small></div><a className="text-action" href="#/mission-control">Return to decision queue</a></section>}
      {mission && <section className="mission-orientation" aria-label="Mission context">
        <div><span className="context-label">Project context</span><h2>{packet.repository || "Project identity unavailable"}</h2><p>{packet.agent_status ? `Directory status: ${packet.agent_status}.` : "Repository coordination state is available."} The A1 packet does not provide a mission catalog or declared objective.</p><a className="text-action" href="#/projects">Inspect project context</a></div>
        <div className="mission-boundary"><strong>Objective not provided</strong><span>Mission selection is unavailable in this source. Read-only inspection remains available.</span></div>
      </section>}
      {mission && <div className="live-overview">
        <Panel className="attention-panel" eyebrow="DECISION QUEUE" title="Your attention is needed" meta={<span>{packet.attention.length} attention items</span>}>
          {packet.attention.length ? <div className="attention-queue-layout"><div className="attention-groups"><div className="attention-group-options" role="listbox" aria-label="Attention groups" aria-activedescendant={selectedAttentionId ? `attention-${selectedAttentionId}` : undefined}>{attentionGroups.slice(0, 5).map((group) => { const first = group.items[0]; return <button type="button" role="option" id={`attention-${first.attention_id}`} aria-selected={selectedAttentionId === first.attention_id} className={`attention-group ${selectedAttentionId === first.attention_id ? "is-selected" : ""}`} key={group.cause} onClick={() => { selectAttention(first.attention_id); setSelectionNotice(null); }}><span className="attention-group-count">{group.items.length}</span><span><strong>{attentionGroupLabel(group.cause)}</strong><small>Source cause: {group.cause}</small></span></button>; })}</div><details className="all-attention"><summary>Inspect all {packet.attention.length} records</summary>{attentionGroups.map((group) => <div key={group.cause}><strong>{attentionGroupLabel(group.cause)} · {group.items.length} records</strong>{group.items.map((item) => <button type="button" key={item.attention_id} onClick={() => { selectAttention(item.attention_id); setSelectionNotice(null); }}>{attentionLabel(item).primary} · {item.attention_id}</button>)}</div>)}</details></div><div className="attention-selection" aria-live="polite">{selectionNotice ? <p role="status">{selectionNotice}</p> : selectedAttention ? renderAttentionDetail(selectedAttention) : <p>Select a group to inspect its first record. Ordering follows source order; no priority is inferred.</p>}</div></div> : <p>No attention items projected. This does not establish health.</p>}
        </Panel>
        <div className="live-instruments">
          <section className="signal-instrument" aria-label="Agent activity"><header><h2>Agent activity</h2><a href="#/agents">Inspect agents</a></header>
            <div className="signal-reading"><strong>{metric("agents_lanes", "active_count")}</strong><span>agents listed active</span></div>
            <div className="agent-identities">{metric("agents_lanes", "active_agent_ids")}</div>
            <p>Directory activity does not prove a running task. Exact source values are in details.</p>
          </section>
          <section className="signal-instrument" aria-label="Runnable frontier"><header><h2>Runnable frontier</h2><a href="#/work-graph">Inspect frontier</a></header>
            <div className="signal-pair"><div><strong>{metric("frontier", "eligible_count")}</strong><span>{metricLabel("eligible_count")}</span></div><div><strong>{metric("frontier", "blocked_count")}</strong><span>{metricLabel("blocked_count")}</span></div></div>
            <p>{sourceStateLabel(packet.views.frontier?.status ?? "UNKNOWN")}. Eligibility is a source state, not permission.</p>
          </section>
          <section className="signal-instrument" aria-label="Verification posture"><header><h2>Verification posture</h2><a href="#/verification">Inspect verification</a></header>
            <div className="signal-pair"><div><strong>{metric("ci_iv", "waiting_ci")}</strong><span>{metricLabel("waiting_ci")}</span></div><div><strong>{metric("ci_iv", "waiting_iv")}</strong><span>{metricLabel("waiting_iv")}</span></div></div>
            <p>CI and independent verification are separate source states.</p>
          </section>
        </div>
      </div>}
      {mission && <div className="freshness-summary"><span className={`freshness-dot freshness-${packet.freshness.state.toLowerCase()}`} aria-hidden="true" /> <strong>{sourceStateLabel(data.source.current ? packet.freshness.state : "OFFLINE")}</strong><span>{freshnessLabel(packet.freshness)}</span><details><summary>Connection and source details</summary><p>Connection: {data.source.current ? "connected to the read adapter" : "disconnected from the read adapter"}. Source freshness: {packet.freshness.state}. Local age: {packet.freshness.age_seconds == null ? "unknown" : `${packet.freshness.age_seconds} seconds`}.</p></details></div>}
      {mission && <h2 className="source-section-title">Source detail</h2>}
      <div className="projection-grid">{keys.map(key => {
        const view = packet.views[key];
        return <Panel key={key} eyebrow={view?.status ?? "UNKNOWN"} title={view ? viewLabel(screen, key) : label(key)}>
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
