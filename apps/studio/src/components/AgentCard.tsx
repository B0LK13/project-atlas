import { Bot, CircleDot, Cpu, Timer } from "lucide-react";
import type { AgentPreview } from "../types";
import { AuthorityMark, WorkflowBadge } from "./StatusLanguage";

export function AgentCard({ agent, small = false }: { agent: AgentPreview; small?: boolean }) {
  return (
    <article className={`agent-card presence-${agent.presence.toLowerCase()} ${small ? "agent-card-small" : ""}`}>
      <header>
        <div className="agent-avatar" aria-hidden="true">
          <Bot size={small ? 15 : 18} />
          <span className="agent-presence-dot" />
        </div>
        <div className="agent-title">
          <strong>{agent.name}</strong>
          <span>{agent.role}</span>
        </div>
        <span className="presence-label"><CircleDot size={10} aria-hidden="true" /> {agent.presence}</span>
      </header>
      {!small ? (
        <dl className="agent-facts">
          <div><dt><Cpu size={12} aria-hidden="true" /> Runtime</dt><dd>{agent.model}</dd></div>
          <div><dt><Timer size={12} aria-hidden="true" /> Elapsed</dt><dd>{agent.elapsed}</dd></div>
          <div><dt>Platform</dt><dd>{agent.platform}</dd></div>
          <div><dt>Lane</dt><dd>{agent.lane ?? "none"}</dd></div>
        </dl>
      ) : null}
      <div className="agent-badges">
        <WorkflowBadge state={agent.workflow} />
        <AuthorityMark authorized={agent.authorized} ownsLane={agent.ownsLane} />
      </div>
      {!small ? <p className="agent-evidence">{agent.evidence}</p> : null}
      {agent.blocker ? <p className="agent-blocker">Blocker · {agent.blocker}</p> : null}
    </article>
  );
}
