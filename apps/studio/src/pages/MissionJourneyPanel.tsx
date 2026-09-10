import { useState, type ReactNode } from "react";
import { Panel } from "../components/Panel";
import type { MissionJourneyProjection, TaskContextProjection } from "../types";

function Value({ value }: { value: unknown }): ReactNode {
  if (value == null || value === "") return <span className="projection-unknown">Unavailable</span>;
  if (Array.isArray(value)) return value.length ? <ul className="source-value-list">{value.map((item, index) => <li key={index}><Value value={item} /></li>)}</ul> : <span>None supplied</span>;
  if (typeof value === "object") return <dl className="projection-fields">{Object.entries(value).slice(0, 12).map(([key, item]) => <div key={key}><dt>{key.replaceAll("_", " ")}</dt><dd><Value value={item} /></dd></div>)}</dl>;
  return String(value);
}

function ContractStatus({ status }: { status: string | undefined }) {
  return <span className={`contract-status contract-status-${(status ?? "unknown").toLowerCase()}`}>{status ?? "UNKNOWN"}</span>;
}

export function MissionJourneyPanel({
  journey,
  loading,
  error,
  taskContext,
  taskLoading,
  taskError,
  onLoadTask,
}: {
  journey: MissionJourneyProjection | null;
  loading: boolean;
  error: string | null;
  taskContext: TaskContextProjection | null;
  taskLoading: boolean;
  taskError: string | null;
  onLoadTask: (lane: string) => void;
}) {
  const [lane, setLane] = useState("");
  if (loading && !journey) return <Panel title="Mission workspace"><p>Loading the supported mission, knowledge and development contracts…</p></Panel>;
  if (error && !journey) return <Panel eyebrow="MISSION JOURNEY UNAVAILABLE" title="Mission workspace unavailable"><p>{error}</p><p>Mission Control remains available for source inspection. Refresh to retry.</p></Panel>;
  if (!journey) return null;
  const mission = journey.mission ?? {};
  const knowledge = journey.knowledge ?? { state: "UNKNOWN", items: [] };
  const development = journey.development ?? {};
  const candidates = Array.isArray((development.candidate_identity as Record<string, unknown> | undefined)?.top_claim_lanes)
    ? (development.candidate_identity as Record<string, unknown>).top_claim_lanes as Array<Record<string, unknown>> : [];
  const nextActions = journey.next_actions ?? {};
  const monitoring = nextActions.monitoring as Record<string, unknown> | undefined;
  const continuity = nextActions.continuity as Record<string, unknown> | undefined;
  const session = nextActions.mission_session as Record<string, unknown> | undefined;
  return <section className="mission-journey" aria-label="Mission workspace">
    <header className="journey-header">
      <div><p className="panel-eyebrow">SUPPORTED READ-ONLY CONTRACT · {journey.schema}</p><h2>Mission workspace</h2><p>{journey.repository ?? "Project identity unavailable"}</p></div>
      <ContractStatus status={String(mission.freshness_state ?? "UNKNOWN")} />
    </header>
    <div className="journey-grid">
      <Panel title="Current mission" meta={<ContractStatus status={String(mission.mission_status ?? "UNKNOWN")} />}>
        <p>The connected contract supplies the current mission state and attention. It does not declare a mission catalog or grant execution permission.</p>
        <dl className="projection-fields"><div><dt>Attention items</dt><dd><Value value={mission.attention_count} /></dd></div><div><dt>Mission snapshot</dt><dd><Value value={mission.snapshot_fingerprint} /></dd></div></dl>
      </Panel>
      <Panel title="Knowledge that matters" meta={<ContractStatus status={knowledge.state} />}>
        {knowledge.items?.length ? <ul className="journey-knowledge">{knowledge.items.slice(0, 6).map((item, index) => <li key={index}><strong>{String(item.title ?? item.path ?? "Knowledge item")}</strong><span>{String(item.kind ?? "source")}</span><small>{String((item.provenance as Record<string, unknown> | undefined)?.source_path ?? "Provenance supplied by contract")}</small></li>)}</ul> : <p>No knowledge items were supplied. That is an explicit state, not permission to guess.</p>}
      </Panel>
      <Panel title="Choose a lane to understand" meta={<span>{candidates.length} candidates</span>}>
        {candidates.length ? <><label htmlFor="journey-lane">Development lane</label><select id="journey-lane" value={lane} onChange={(event) => setLane(event.target.value)}><option value="">Select a lane</option>{candidates.map((candidate, index) => <option key={index} value={String(candidate.lane ?? "")}>{String(candidate.lane ?? "Unknown lane")} · {String(candidate.action_class ?? "UNKNOWN")}</option>)}</select><button className="inspection-button" disabled={!lane || taskLoading} onClick={() => onLoadTask(lane)}>{taskLoading ? "Loading task context…" : "Inspect task context"}</button></> : <p>No lane candidates were supplied. The development contract remains explicit about missing context.</p>}
        {taskError && <p role="alert">{taskError}</p>}
      </Panel>
      <Panel title="Next permitted action" eyebrow="PERMITTED ≠ AUTHORIZED">
        <p>The contract may identify a supported next step, but this UI never turns it into an execution control.</p>
        <Value value={nextActions.claim_candidates} />
        <p>Use the selected lane's Task Context for prerequisites and authorization boundaries.</p>
      </Panel>
    </div>
    {taskContext && <section className="task-context" aria-label="Task context"><header><h2>Task context · {taskContext.lane}</h2><ContractStatus status={String(taskContext.freshness.state ?? "UNKNOWN")} /></header><div className="journey-grid"><Panel title="Lane state"><Value value={taskContext.lane_state} /></Panel><Panel title="Knowledge lenses"><Value value={taskContext.knowledge} /></Panel><Panel title="Supported next step"><Value value={taskContext.next_step} /><p>Authorization: NOT_GRANTED_BY_THIS_PACKET</p></Panel><Panel title="Recovery and continuity"><Value value={taskContext.recovery} /><Value value={taskContext.continuation} /></Panel></div><Panel title="Missing inputs"><Value value={taskContext.missing} /></Panel></section>}
    <Panel title="Continue safely" eyebrow="INSPECT · MONITOR · RESUME">
      <p>These are supported external handoffs from the contract. They do not execute from Studio.</p>
      <ul className="contract-handoffs">{[monitoring, continuity, session].filter(Boolean).map((action, index) => <li key={index}><strong>{["Monitor outcome evidence", "Inspect intent continuity", "Inspect mission session"][index]}</strong><code>{String(action?.command ?? "Command unavailable")}</code><span>Auto-retry: forbidden · authority: none</span></li>)}</ul>
    </Panel>
  </section>;
}
