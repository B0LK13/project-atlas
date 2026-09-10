import { ArrowLeft, ArrowRight, Check, CircleDot, Columns3, GitCommitHorizontal, Orbit, Rows3, Sparkles } from "lucide-react";
import type { StudioEnvelope } from "../types";
import { TruthBadge } from "../components/StatusLanguage";

type Direction = "overview" | "orbital" | "workbench" | "twin";

const directions = [
  {
    id: "orbital" as const,
    code: "DIRECTION A",
    title: "Orbital Mission Control",
    subtitle: "Spatial command surface",
    description: "A central objective with agents and gates arranged as an operational constellation.",
    traits: ["low chrome", "spatial hierarchy", "agent-forward"],
    score: "SPATIAL",
    icon: Orbit,
  },
  {
    id: "workbench" as const,
    code: "DIRECTION B",
    title: "Evidence Workbench",
    subtitle: "Dense developer instrument",
    description: "A keyboard-first evidence desk with ledgers, exact objects and verification in permanent view.",
    traits: ["maximum density", "evidence-forward", "low ambiguity"],
    score: "DENSE",
    icon: Columns3,
  },
  {
    id: "twin" as const,
    code: "DIRECTION C · SELECTED",
    title: "Living Project Twin",
    subtitle: "Temporal project intelligence",
    description: "A living mission thread that exposes how intent becomes evidence, knowledge and next action.",
    traits: ["narrative topology", "calm density", "distinct Atlas identity"],
    score: "TEMPORAL",
    icon: Rows3,
  },
];

export function DesignLabPage({ data }: { data: StudioEnvelope }) {
  const hashDirection = window.location.hash.split("/").at(-1);
  const initial: Direction = hashDirection === "orbital" || hashDirection === "workbench" || hashDirection === "twin" ? hashDirection : "overview";
  const direction = initial;
  const navigate = (target: Direction) => {
    window.location.hash = target === "overview" ? "/design-lab" : `/design-lab/${target}`;
  };
  if (direction === "orbital") return <OrbitalPrototype data={data} onBack={() => navigate("overview")} />;
  if (direction === "workbench") return <WorkbenchPrototype data={data} onBack={() => navigate("overview")} />;
  if (direction === "twin") return <TwinPrototype data={data} onBack={() => navigate("overview")} />;

  return (
    <div className="screen design-lab-page">
      <header className="screen-header design-lab-header">
        <div><p>DESIGN LAB / PRESERVED EVIDENCE</p><h1>Three ways Atlas could feel alive</h1><span>Substantially different hierarchy, density, navigation and truth representation—evaluated before convergence.</span></div>
        <div className="selection-seal"><Check size={15} /><span><strong>DIRECTION C SELECTED</strong><small>Design judgment · temporal clarity and calm density</small></span></div>
      </header>
      <div className="direction-grid">
        {directions.map((item) => {
          const Icon = item.icon;
          return (
            <article key={item.id} className={`direction-card direction-${item.id} ${item.id === "twin" ? "is-selected" : ""}`}>
              <div className="direction-preview" aria-hidden="true"><Icon size={30} /><span /><i /><i /><i /></div>
              <div className="direction-code"><span>{item.code}</span><b>{item.score}</b></div>
              <h2>{item.title}</h2><h3>{item.subtitle}</h3><p>{item.description}</p>
              <div className="direction-traits">{item.traits.map((trait) => <span key={trait}>{trait}</span>)}</div>
              <button onClick={() => navigate(item.id)}>Explore prototype <ArrowRight size={14} /></button>
            </article>
          );
        })}
      </div>
      <section className="decision-matrix" aria-labelledby="decision-matrix-title">
        <header><div><p>PRODUCT DECISION</p><h2 id="decision-matrix-title">Why the Project Twin converged</h2></div><span>Scores are design judgment · not Atlas truth</span></header>
        <div className="matrix-table" role="table">
          <div role="row" className="matrix-head"><span>Direction</span><span>10s clarity</span><span>Density</span><span>Truth language</span><span>Scalability</span><span>Identity</span><span>Total</span></div>
          <div role="row"><strong>Orbital</strong><span>8.6</span><span>6.4</span><span>7.8</span><span>7.1</span><span>9.1</span><b>7.8</b></div>
          <div role="row"><strong>Workbench</strong><span>8.1</span><span>9.6</span><span>9.0</span><span>8.8</span><span>5.7</span><b>8.2</b></div>
          <div role="row" className="matrix-selected"><strong>Living Twin</strong><span>9.4</span><span>8.8</span><span>9.2</span><span>9.1</span><span>9.3</span><b>9.1</b></div>
        </div>
      </section>
    </div>
  );
}

function PrototypeHeader({ code, title, onBack }: { code: string; title: string; onBack: () => void }) {
  return <header className="prototype-header"><button onClick={onBack}><ArrowLeft size={14} /> All directions</button><span>{code}</span><h1>{title}</h1><b>DESIGN_PREVIEW · FIXTURE != LIVE</b></header>;
}

function OrbitalPrototype({ data, onBack }: { data: StudioEnvelope; onBack: () => void }) {
  const agents = data.preview?.agents ?? [];
  return (
    <div className="design-prototype prototype-orbital">
      <PrototypeHeader code="DIRECTION A / SPATIAL" title="Orbital Mission Control" onBack={onBack} />
      <div className="orbital-field">
        <div className="orbit-ring ring-one" /><div className="orbit-ring ring-two" />
        <article className="orbit-core"><Sparkles size={18} /><span>CURRENT OBJECTIVE</span><h2>{data.preview?.objective}</h2><p>{data.preview?.objectiveDetail}</p><strong>{data.projection.mission_status.replaceAll("_", " ")}</strong></article>
        {agents.map((agent, index) => <article key={agent.id} className={`orbit-agent orbit-agent-${index + 1}`}><CircleDot size={12} /><span>{agent.presence}</span><strong>{agent.name}</strong><small>{agent.role}</small></article>)}
        <article className="orbit-gate"><span>OWNER GATE</span><strong>IV unbound</strong><small>attention ≠ authorization</small></article>
        <div className="orbit-coordinates">AXIS / INTENT → EVIDENCE<br />FIELD / AGENT ACTIVITY<br />DEPTH / CERTAINTY</div>
      </div>
    </div>
  );
}

function WorkbenchPrototype({ data, onBack }: { data: StudioEnvelope; onBack: () => void }) {
  const preview = data.preview;
  return (
    <div className="design-prototype prototype-workbench">
      <PrototypeHeader code="DIRECTION B / DENSE" title="Evidence Workbench" onBack={onBack} />
      <div className="workbench-toolbar"><span>PROJECT ATLAS</span><code>{preview?.repository.branch}</code><strong>HEAD {preview?.repository.head.slice(0, 9)}</strong><b>{data.projection.freshness.state}</b></div>
      <div className="workbench-grid">
        <section><header><span>01</span><strong>FRONTIER</strong></header>{preview?.nodes.slice(0, 5).map((node) => <div className="wb-row" key={node.id}><i className={`wb-dot dot-${node.state}`} /><code>{node.id}</code><span>{node.state}</span><TruthBadge state={node.truth} compact /></div>)}</section>
        <section><header><span>02</span><strong>AGENTS</strong></header>{preview?.agents.map((agent) => <div className="wb-agent" key={agent.id}><strong>{agent.name}</strong><span>{agent.role}</span><code>{agent.presence} / {agent.authorized ? "SCOPED" : "NO AUTH"}</code></div>)}</section>
        <section className="wb-evidence"><header><span>03</span><strong>EVIDENCE</strong></header>{data.projection.attention.map((item) => <div key={item.attention_id}><AlertGlyph /><strong>{item.title}</strong><p>{item.detail}</p><code>{item.kind}</code></div>)}</section>
        <section className="wb-log"><header><span>04</span><strong>CHRONICLE</strong></header>{preview?.chronicle.map((event) => <div key={event.id}><time>{event.time}</time><span>{event.kind}</span><strong>{event.title}</strong></div>)}</section>
      </div>
    </div>
  );
}

function AlertGlyph() {
  return <span className="alert-glyph" aria-hidden="true">!</span>;
}

function TwinPrototype({ data, onBack }: { data: StudioEnvelope; onBack: () => void }) {
  const nodes = data.preview?.nodes ?? [];
  return (
    <div className="design-prototype prototype-twin">
      <PrototypeHeader code="DIRECTION C / SELECTED" title="Living Project Twin" onBack={onBack} />
      <div className="twin-heading"><div><span>PROJECT PULSE / A-01</span><h2>{data.preview?.objective}</h2></div><strong><CircleDot size={12} /> {data.projection.mission_status.replaceAll("_", " ")}</strong></div>
      <div className="twin-thread">
        {nodes.map((node, index) => <article key={node.id} className={`${node.current ? "is-current" : ""} twin-node-${node.state}`}><span className="twin-index">{String(index + 1).padStart(2, "0")}</span><div className="twin-axis"><i /><GitCommitHorizontal size={16} /></div><div><small>{node.eyebrow}</small><h3>{node.label}</h3><p>{node.detail}</p><footer><TruthBadge state={node.truth} compact /><span>{node.owner ?? "UNOWNED"}</span></footer></div></article>)}
      </div>
      <aside className="twin-evidence-rail"><span>EVIDENCE RAIL</span>{data.projection.attention.map((item) => <article key={item.attention_id}><b>{item.kind}</b><strong>{item.title}</strong><small>{item.detail}</small></article>)}</aside>
    </div>
  );
}
