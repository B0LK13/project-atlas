import { AlertTriangle, ArrowRight, Asterisk, CircleDot, GitBranch, ShieldAlert, Sparkles } from "lucide-react";
import type { StudioEnvelope } from "../types";
import { AgentCard } from "../components/AgentCard";
import { EmptyState } from "../components/EmptyState";
import { Panel } from "../components/Panel";
import { TruthBadge } from "../components/StatusLanguage";
import { VerificationPipeline } from "../components/VerificationPipeline";
import { WorkGraph } from "../components/WorkGraph";

export function MissionControlPage({ data, onNavigate }: { data: StudioEnvelope; onNavigate: (id: "agents" | "work-graph" | "verification" | "chronicle") => void }) {
  const { projection, preview } = data;
  const objective = preview?.objective ?? "Current objective unavailable";
  const objectiveDetail = preview?.objectiveDetail ?? "The A1 projection does not currently expose a typed objective.";
  const fingerprint = projection.snapshot_fingerprint.slice(0, 12);
  const topAttention = projection.attention.slice(0, 3);
  const currentNode = preview?.nodes.find((node) => node.current);

  return (
    <div className="screen mission-control-page">
      <header className="mission-header">
        <div className="mission-coordinate">
          <span>PROJECT / A-01</span>
          <strong>Project Atlas</strong>
          <small><GitBranch size={12} aria-hidden="true" /> {projection.repository}</small>
        </div>
        <div className="mission-title">
          <p><Sparkles size={13} aria-hidden="true" /> ACTIVE MISSION</p>
          <h1>{objective}</h1>
          <span>{objectiveDetail}</span>
        </div>
        <div className="mission-status-block">
          <span>MISSION STATE</span>
          <strong className={`mission-state state-${projection.mission_status.toLowerCase()}`}><CircleDot size={12} aria-hidden="true" /> {projection.mission_status.replaceAll("_", " ")}</strong>
          <small>{projection.freshness.state} · fp {fingerprint}</small>
        </div>
      </header>

      <section className="attention-strip" aria-label="Attention requiring review">
        <div className="attention-label"><ShieldAlert size={16} aria-hidden="true" /><span><strong>ATTENTION</strong><small>≠ authorization</small></span></div>
        <div className="attention-items">
          {topAttention.length ? topAttention.map((item, index) => (
            <article key={item.attention_id} className={`attention-item attention-tier-${Math.min(index + 1, 3)}`}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <div><strong>{item.title}</strong><small>{item.detail ?? item.kind}</small></div>
              <ArrowRight size={13} aria-hidden="true" />
            </article>
          )) : <span className="attention-empty">No attention items projected. This does not imply healthy.</span>}
        </div>
      </section>

      <div className="mission-grid">
        <Panel eyebrow="OPERATING ENTITIES" title="Active agents" className="agents-panel" meta={<span className="metric-pill">{preview?.agents.filter((agent) => agent.presence === "ACTIVE").length ?? 0} ACTIVE</span>} action={{ label: "Open all agents", onClick: () => onNavigate("agents") }}>
          <div className="agent-mini-list">
            {preview?.agents.length ? preview.agents.slice(0, 3).map((agent) => <AgentCard key={agent.id} agent={agent} small />) : <EmptyState title="No active agents" detail="Agent detail is absent from the current projection." />}
          </div>
        </Panel>

        <Panel eyebrow="CURRENT FRONTIER" title="Mission thread" className="graph-panel" meta={currentNode ? <span className="metric-pill active"><Asterisk size={11} /> {currentNode.label}</span> : <span className="metric-pill">UNKNOWN</span>} action={{ label: "Open work graph", onClick: () => onNavigate("work-graph") }}>
          <WorkGraph nodes={preview?.nodes ?? []} edges={preview?.edges ?? []} compact />
        </Panel>

        <Panel eyebrow="PROOF CHAIN" title="Verification pipeline" className="verification-panel" meta={<span className="metric-pill muted">CI ≠ IV ≠ MERGE</span>} action={{ label: "Open verification", onClick: () => onNavigate("verification") }}>
          <VerificationPipeline stages={preview?.verification ?? []} />
        </Panel>

        <Panel eyebrow="RECENT SIGNALS" title="Chronicle" className="chronicle-panel" action={{ label: "Open Chronicle", onClick: () => onNavigate("chronicle") }}>
          {preview?.chronicle.length ? (
            <ol className="chronicle-compact">
              {preview.chronicle.slice(-4).reverse().map((event) => (
                <li key={event.id}>
                  <time>{event.time}</time>
                  <i />
                  <div><strong>{event.title}</strong><small>{event.actor} · {event.kind}</small></div>
                  <TruthBadge state={event.truth} compact />
                </li>
              ))}
            </ol>
          ) : <EmptyState title="No recent activity" detail="The projection contains no observation events." />}
        </Panel>

        <Panel eyebrow="PROJECT INTELLIGENCE" title="Known / uncertain" className="intelligence-panel" meta={<span className="metric-pill warning"><AlertTriangle size={11} /> 2 SIGNALS</span>}>
          <div className="intelligence-list">
            {(preview?.knowledge ?? []).slice(0, 3).map((item) => (
              <article key={item.id}>
                <TruthBadge state={item.truth} compact />
                <div><strong>{item.title}</strong><p>{item.summary}</p><small>{item.source}</small></div>
              </article>
            ))}
            {!preview?.knowledge.length ? <EmptyState title="Knowledge detail unavailable" detail="No source-backed concept cards are wired into this projection." /> : null}
          </div>
        </Panel>
      </div>
    </div>
  );
}
