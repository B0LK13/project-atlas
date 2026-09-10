import {
  AlertTriangle,
  ArrowRight,
  Bot,
  Braces,
  Check,
  CircleDashed,
  Clock3,
  Copy,
  FileCode2,
  FolderGit2,
  GitBranch,
  GitPullRequest,
  Layers3,
  LockKeyhole,
  Search,
  Shield,
  ShieldCheck,
} from "lucide-react";
import type { ReactNode } from "react";
import type { DensityMode, StudioEnvelope, ThemeMode } from "../types";
import type { SourcePreference } from "../data/useStudioData";
import { AgentCard } from "../components/AgentCard";
import { EmptyState } from "../components/EmptyState";
import { Panel } from "../components/Panel";
import { TruthBadge } from "../components/StatusLanguage";
import { VerificationPipeline } from "../components/VerificationPipeline";
import { WorkGraph } from "../components/WorkGraph";

function ScreenHeader({ eyebrow, title, description, aside }: { eyebrow: string; title: string; description: string; aside?: ReactNode }) {
  return (
    <header className="screen-header">
      <div><p>{eyebrow}</p><h1>{title}</h1><span>{description}</span></div>
      {aside ? <div className="screen-header-aside">{aside}</div> : null}
    </header>
  );
}

export function ProjectsPage({ data }: { data: StudioEnvelope }) {
  const projection = data.projection;
  return (
    <div className="screen">
      <ScreenHeader eyebrow="PORTFOLIO / READ PLANE" title="Projects" description="Project identity, current mission and evidence posture—without turning federation into authority." aside={<span className="large-coordinate">01 PROJECT</span>} />
      <div className="project-card-grid">
        <article className="project-card project-card-primary">
          <div className="project-card-map" aria-hidden="true"><i /><i /><i /><span>A/01</span></div>
          <div className="project-card-content">
            <p>ACTIVE COORDINATE · A/01</p>
            <h2>Project Atlas</h2>
            <span>{projection.repository}</span>
            <dl>
              <div><dt>Mission</dt><dd>{data.preview?.objective ?? "UNKNOWN"}</dd></div>
              <div><dt>State</dt><dd>{projection.mission_status.replaceAll("_", " ")}</dd></div>
              <div><dt>Freshness</dt><dd>{projection.freshness.state}</dd></div>
              <div><dt>Projection</dt><dd>{projection.schema}</dd></div>
            </dl>
            <a className="text-action" href="#/mission-control">Current workspace <ArrowRight size={14} aria-hidden="true" /></a>
          </div>
        </article>
        <div className="project-empty-slot">
          <CircleDashed size={25} aria-hidden="true" />
          <div><strong>No second project loaded</strong><p>Portfolio breadth is unknown. Studio does not invent projects to fill the grid.</p></div>
        </div>
      </div>
      <section className="workspace-map" aria-labelledby="workspace-map-title">
        <header><div><p>PROJECT WORKSPACE</p><h2 id="workspace-map-title">Information architecture</h2></div><span>Selected views are wired in this mission</span></header>
        <div className="workspace-sections">
          {["Overview", "Goals", "Ideas", "Research", "Architecture", "Requirements", "Roadmap", "DAG", "Agents", "Repository", "Tests", "CI", "Verification", "Knowledge", "Decisions", "History", "Metrics"].map((section, index) => (
            <div key={section} className={index > 12 && data.source.kind !== "DESIGN_PREVIEW" ? "is-unwired" : ""}>
              <span>{String(index + 1).padStart(2, "0")}</span><strong>{section}</strong><small>{index < 7 ? "shell" : index < 13 ? "read view" : "future / not wired"}</small>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export function AgentsPage({ data }: { data: StudioEnvelope }) {
  const agents = data.preview?.agents ?? [];
  return (
    <div className="screen">
      <ScreenHeader eyebrow="AGENT PLANE / ENTITY VIEW" title="Operating entities" description="Existence, activity, authorization and lane ownership are four separate signals." aside={<div className="header-stats"><span><b>{agents.filter((agent) => agent.exists).length}</b> exist</span><span><b>{agents.filter((agent) => agent.presence === "ACTIVE").length}</b> active</span><span><b>{agents.filter((agent) => agent.ownsLane).length}</b> own lane</span></div>} />
      {agents.length ? <div className="agent-grid">{agents.map((agent) => <AgentCard key={agent.id} agent={agent} />)}</div> : <EmptyState title="No agent registry detail" detail="The typed projection reports no inspectable operating entities." />}
      <Panel eyebrow="SEMANTIC SEPARATION" title="What each signal means" className="agent-semantics">
        <div className="semantic-grid">
          <div><Bot size={17} /><strong>Exists</strong><p>Present in a registry or evidence source. It may still be inactive.</p></div>
          <div><Clock3 size={17} /><strong>Active</strong><p>Recent runtime activity was observed. Activity grants no authority.</p></div>
          <div><Shield size={17} /><strong>Authorized</strong><p>A scoped external grant exists. UI state cannot mint one.</p></div>
          <div><Layers3 size={17} /><strong>Own lane</strong><p>The agent is bound to a specific work lane at an exact state.</p></div>
        </div>
      </Panel>
    </div>
  );
}

export function WorkGraphPage({ data }: { data: StudioEnvelope }) {
  return (
    <div className="screen graph-screen">
      <ScreenHeader eyebrow="DAG / COORDINATION PROJECTION" title="Work graph" description="A navigable map of dependency and frontier state. Selection explains; it never authorizes." aside={<span className="read-only-stamp"><LockKeyhole size={13} /> VISUALIZATION ONLY</span>} />
      <div className="graph-layout">
        <Panel eyebrow="ATLAS COORDINATES" title="Mission topology" className="graph-full-panel" meta={<span className="metric-pill active">FOCUS · CURRENT FRONTIER</span>}>
          <WorkGraph nodes={data.preview?.nodes ?? []} edges={data.preview?.edges ?? []} />
        </Panel>
        <aside className="graph-legend panel">
          <header className="panel-header"><div><p className="panel-eyebrow">LEGEND</p><h2>Graph state</h2></div></header>
          <div className="panel-body">
            {["unowned", "owned", "runnable", "blocked", "frozen", "implementation", "CI", "IV", "merge-ready", "merged", "sealed", "superseded"].map((state) => <span key={state} className={`legend-state state-${state.toLowerCase()}`}><i /> {state}</span>)}
            <p className="legend-note">Unknown remains visible when a typed source omits a state.</p>
          </div>
        </aside>
      </div>
    </div>
  );
}

export function RepositoryPage({ data }: { data: StudioEnvelope }) {
  const repository = data.preview?.repository;
  return (
    <div className="screen">
      <ScreenHeader eyebrow="REPOSITORY / EXACT OBJECTS" title="Repository & changes" description="Progressive disclosure keeps exact identity available without making every user parse Git internals." aside={<span className="read-only-stamp"><GitBranch size={13} /> READ ONLY</span>} />
      {repository ? (
        <>
          <div className="object-strip">
            {[{ label: "BRANCH", value: repository.branch }, { label: "HEAD", value: repository.head }, { label: "TREE", value: repository.tree }, { label: "BASE", value: repository.base }].map((item) => (
              <div key={item.label}><span>{item.label}</span><code title={item.value}>{item.value}</code><button aria-label={`Copy ${item.label}`} disabled title="Copy is a local presentation action; disabled in this preview"><Copy size={12} /></button></div>
            ))}
          </div>
          <div className="repo-grid">
            <Panel eyebrow="WORKING SET" title="Changed files" meta={<span className="metric-pill">{repository.files.length} FILES · {repository.state}</span>}>
              <div className="file-table" role="table" aria-label="Changed files">
                {repository.files.map((file) => (
                  <div role="row" key={file.path}><span className={`file-state state-${file.state}`}>{file.state[0].toUpperCase()}</span><FileCode2 size={14} aria-hidden="true" /><code>{file.path}</code><span className="file-delta"><b>+{file.additions}</b><i>-{file.deletions}</i></span></div>
                ))}
              </div>
            </Panel>
            <Panel eyebrow="RELATIONSHIP" title="Stack identity">
              <div className="stack-identity">
                <FolderGit2 size={24} aria-hidden="true" />
                <p><strong>Visual shell lane</strong><span>stacks on PR #770</span></p>
                <ArrowRight size={15} aria-hidden="true" />
                <p><strong>A1 Mission Control</strong><span>stacks on PR #763</span></p>
                <ArrowRight size={15} aria-hidden="true" />
                <p><strong>A0 foundation</strong><span>open / not merged</span></p>
              </div>
              <div className="boundary-callout"><AlertTriangle size={15} /><span><strong>Candidate identity only</strong>Open PRs are not merged Atlas truth.</span></div>
            </Panel>
          </div>
        </>
      ) : <EmptyState title="Git detail not wired" detail="The live A1 projection does not expose this repository detail surface." />}
    </div>
  );
}

export function VerificationPage({ data }: { data: StudioEnvelope }) {
  const stages = data.preview?.verification ?? [];
  return (
    <div className="screen">
      <ScreenHeader eyebrow="EVIDENCE / GATED PROGRESSION" title="CI & Verification" description="Each stage has its own evidence and authority boundary. Completion never auto-authorizes the next stage." aside={<span className="large-coordinate">{stages.filter((stage) => stage.state === "VERIFIED").length}/{stages.length || 0} VERIFIED</span>} />
      <Panel eyebrow="CANDIDATE PIPELINE" title="From implementation to seal" className="verification-main">
        <VerificationPipeline stages={stages} detailed />
      </Panel>
      <div className="verification-grid">
        <Panel eyebrow="INVARIANT" title="CI is not IV"><div className="invariant-card"><Braces size={22} /><p><strong>CI</strong><span>Repository automation over a candidate object.</span></p><span>≠</span><p><strong>IV</strong><span>Independent verifier judgment bound to the same object.</span></p></div></Panel>
        <Panel eyebrow="OWNER BOUNDARY" title="Merge stays gated"><div className="future-action"><button disabled><GitPullRequest size={15} /> Merge candidate</button><span>FUTURE CAPABILITY · OWNER AUTHORITY REQUIRED</span></div></Panel>
        <Panel eyebrow="EVIDENCE HEALTH" title="Current posture"><ul className="evidence-list"><li><Check size={13} /> Base A0/A1 tests observed locally</li><li><CircleDashed size={13} /> Final desktop candidate not frozen</li><li><CircleDashed size={13} /> CI not attached</li><li><CircleDashed size={13} /> Formal IV not assigned</li></ul></Panel>
      </div>
    </div>
  );
}

export function KnowledgePage({ data }: { data: StudioEnvelope }) {
  const knowledge = data.preview?.knowledge ?? [];
  return (
    <div className="screen">
      <ScreenHeader eyebrow="KNOWLEDGE / PROVENANCE VIEW" title="What we know—and why" description="Concepts are organized around claims, sources, currency and conflict rather than folders." aside={<button className="filter-button" disabled title="Preview catalog filtering is not implemented"><Search size={14} /> Filter knowledge · preview only</button>} />
      {knowledge.length ? <div className="knowledge-grid">{knowledge.map((item) => (
        <article key={item.id} className={`knowledge-card knowledge-${item.truth.toLowerCase()}`}>
          <header><TruthBadge state={item.truth} /><span>{item.id}</span></header>
          <h2>{item.title}</h2><p>{item.summary}</p>
          {item.conflict ? <div className="conflict-line"><AlertTriangle size={13} /> {item.conflict}</div> : null}
          <footer><span><strong>SOURCE</strong>{item.source}</span><span><strong>CURRENCY</strong>{item.age}</span></footer>
        </article>
      ))}</div> : <EmptyState title="Knowledge source unavailable" detail="No typed knowledge cards are attached to this projection." />}
    </div>
  );
}

export function ChroniclePage({ data }: { data: StudioEnvelope }) {
  const chronicle = data.preview?.chronicle ?? [];
  return (
    <div className="screen">
      <ScreenHeader eyebrow="CHRONICLE / OBSERVABLE HISTORY" title="What happened while you were away" description="A persistent sequence of evidence-backed events. Recorded activity is not hidden model reasoning." aside={<span className="read-only-stamp"><Clock3 size={13} /> {chronicle.length} EVENTS</span>} />
      {chronicle.length ? <ol className="chronicle-timeline">{chronicle.slice().reverse().map((event, index) => (
        <li key={event.id}>
          <div className="timeline-time"><time>{event.time}</time><span>SEP 09</span></div>
          <div className="timeline-axis"><i /><span>{String(chronicle.length - index).padStart(2, "0")}</span></div>
          <article><header><span>{event.kind}</span><TruthBadge state={event.truth} compact /></header><h2>{event.title}</h2><p>{event.detail}</p><footer>{event.actor} · {event.id}</footer></article>
        </li>
      ))}</ol> : <EmptyState title="No Chronicle events" detail="Nothing observable was included in this projection." />}
    </div>
  );
}

export function SettingsPage({
  data,
  theme,
  density,
  preference,
  onTheme,
  onDensity,
  onPreference,
}: {
  data: StudioEnvelope;
  theme: ThemeMode;
  density: DensityMode;
  preference: SourcePreference;
  onTheme: (theme: ThemeMode) => void;
  onDensity: (density: DensityMode) => void;
  onPreference: (preference: SourcePreference) => void;
}) {
  return (
    <div className="screen settings-screen">
      <ScreenHeader eyebrow="STUDIO / LOCAL ENVIRONMENT" title="Environment" description="Presentation settings and read-source selection. No Atlas truth or repository state is written here." />
      <div className="settings-grid">
        <Panel eyebrow="DATA BOUNDARY" title="Projection source">
          <div className="segmented-control" role="group" aria-label="Projection source">
            <button className={preference === "projection" ? "is-active" : ""} onClick={() => onPreference("projection")}><ShieldCheck size={14} /> A1 projection</button>
            <button className={preference === "fixture" ? "is-active" : ""} onClick={() => onPreference("fixture")}><Braces size={14} /> Design fixture</button>
          </div>
          <div className="settings-status"><span>Current</span><strong>{data.source.label}</strong><p>{data.source.detail}</p></div>
        </Panel>
        <Panel eyebrow="APPEARANCE" title="Theme">
          <div className="option-grid"><button className={theme === "dark" ? "is-active" : ""} onClick={() => onTheme("dark")}><span className="theme-preview preview-dark" /><strong>Atlas dark</strong><small>Deep layered technical surfaces</small></button><button className={theme === "light" ? "is-active" : ""} onClick={() => onTheme("light")}><span className="theme-preview preview-light" /><strong>Atlas light</strong><small>Paper-white evidence workspace</small></button></div>
        </Panel>
        <Panel eyebrow="INFORMATION DENSITY" title="Workspace density">
          <div className="density-options">{(["comfortable", "compact", "focus"] as const).map((mode) => <button key={mode} className={density === mode ? "is-active" : ""} onClick={() => onDensity(mode)}><span>{mode}</span><small>{mode === "comfortable" ? "balanced spacing" : mode === "compact" ? "maximum signal" : "single-plane emphasis"}</small></button>)}</div>
        </Panel>
        <Panel eyebrow="RUNTIME INVENTORY" title="Linux shell">
          <dl className="runtime-list"><div><dt>Platform</dt><dd>Linux first</dd></div><div><dt>Desktop shell</dt><dd>Tauri 2</dd></div><div><dt>Frontend</dt><dd>React + TypeScript</dd></div><div><dt>Native commands</dt><dd>0</dd></div><div><dt>Shell plugin</dt><dd>not installed</dd></div><div><dt>Bridge</dt><dd>localhost · GET only</dd></div></dl>
        </Panel>
      </div>
    </div>
  );
}
