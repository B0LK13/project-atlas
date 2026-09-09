import type { ScreenId, StudioEnvelope } from "../types";
import { Panel } from "../components/Panel";

const views: Partial<Record<ScreenId, string[]>> = {
  agents: ["agents_lanes", "ownership"], "work-graph": ["frontier", "ownership"],
  repository: ["stacks"], verification: ["ci_iv", "human_gates", "evidence", "postmerge_seal"],
  knowledge: [], chronicle: ["telemetry"], projects: ["health", "residuals"],
};

export function ProjectionPage({ data, screen }: { data: StudioEnvelope; screen: ScreenId }) {
  const packet = data.projection;
  const keys = screen === "mission-control" ? Object.keys(packet.views) : views[screen] ?? [];
  return <div className="screen projection-screen">
    <header className="screen-header"><div><p>A1 / READ-ONLY PROJECTION</p>
      <h1>{screen.replaceAll("-", " ")}</h1>
      <span>{packet.repository || "Project identity unavailable"}</span></div>
      <strong>{packet.mission_status} · {packet.freshness.state}</strong>
    </header>
    <p>{data.source.detail}</p>
    {data.source.kind === "UNAVAILABLE" ? <Panel eyebrow="DISCONNECTED" title="Projection unavailable">
      <p>No operational state is available. Refresh to retry, or explicitly select Design fixture in Environment.</p>
    </Panel> : <>
      <Panel eyebrow="ATTENTION ≠ AUTHORIZATION" title="Attention">
        {packet.attention.length ? packet.attention.map(item => <article key={item.attention_id}>
          <h3>{item.title}</h3><p>{item.kind} · tier {item.tier}</p><p>{item.detail}</p>
        </article>) : <p>No attention items supplied by this projection.</p>}
      </Panel>
      <div className="projection-grid">{keys.map(key => {
        const view = packet.views[key];
        return <Panel key={key} eyebrow={view?.status ?? "UNKNOWN"} title={key.replaceAll("_", " ")}>
          {view ? <>
            {view.notes.map((note, index) => <p key={index}>{note}</p>)}
            {view.summary && Object.keys(view.summary).length ? <dl className="projection-fields">
              {Object.entries(view.summary).map(([field, value]) => <div key={field}>
                <dt>{field.replaceAll("_", " ")}</dt>
                <dd>{value == null ? "Unavailable" : typeof value === "object" ? <pre>{JSON.stringify(value, null, 2)}</pre> : String(value)}</dd>
              </div>)}
            </dl> : <p>Summary unavailable.</p>}
          </> : <p>This view is unavailable in the supplied contract.</p>}
        </Panel>;
      })}</div>
      {!keys.length && <Panel eyebrow="NOT WIRED" title="Detail projection unavailable"><p>A1 does not supply this detail view. Demonstration content is available only in explicitly selected fixture mode.</p></Panel>}
      <details><summary>Projection provenance</summary><dl className="projection-fields">
        <div><dt>Generated at (source supplied)</dt><dd>{packet.generated_at_utc}</dd></div>
        <div><dt>Fingerprint</dt><dd>{packet.snapshot_fingerprint}</dd></div>
        <div><dt>Generator</dt><dd>{packet.provenance.generator}</dd></div>
      </dl></details>
    </>}
  </div>;
}
