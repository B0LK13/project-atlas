import { ProdShell } from "../../components/ProdShell";

/**
 * Derived impact graph lens — Graph ≠ authority.
 * Missing impact-graph.json → unknown, never fabricated edges.
 */
export default function GraphPage() {
  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Graph</p>
          <h1>Impact graph</h1>
          <p className="lede">
            Derived impact projection consume only. Graph is never authority and
            never picks claim winners in the UI.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">graph_authority=false</span>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">unknown≠healthy</span>
          </p>
        </header>

        <section className="panel" aria-label="Impact graph">
          <h2>Projection</h2>
          <p className="banner warn">
            unknown — no live impact-graph file in the static shell; use{" "}
            <code>web_api.impact_graph_summary(vault)</code> for fixture gates.
          </p>
          <p className="disclaimer">Graph ≠ authority · derived indexes only</p>
        </section>
      </main>
    </ProdShell>
  );
}
