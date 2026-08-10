import { ProdShell } from "../../components/ProdShell";
import { useLiveGraph } from "../../hooks/useLiveGraph";

/**
 * Derived impact graph lens — Graph ≠ authority.
 * LIVE_API preferred; demo fallback stays unknown (never fabricated edges).
 */
export default function GraphPage() {
  const { graph, error, loading, dataSource } = useLiveGraph();
  const isDemo = dataSource === "demo_stub";

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
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Graph unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}

        <section className="panel" aria-label="Impact graph">
          <h2>Projection</h2>
          {isDemo ? (
            <p className="banner warn">
              DEMO STUB isolated — no live graph projection; not vault truth
            </p>
          ) : null}
          {!loading && !graph ? (
            <p className="banner warn">unknown — no graph summary available</p>
          ) : null}
          {graph ? (
            <dl className="grid">
              <div>
                <dt>Authority</dt>
                <dd>{String(graph.authority ?? "derived")}</dd>
              </div>
              <div>
                <dt>Available</dt>
                <dd>{String(graph.available ?? "unknown")}</dd>
              </div>
              <div>
                <dt>Nodes</dt>
                <dd>{String(graph.node_count ?? "unknown")}</dd>
              </div>
              <div>
                <dt>Edges</dt>
                <dd>{String(graph.edge_count ?? "unknown")}</dd>
              </div>
            </dl>
          ) : null}
          <p className="disclaimer">
            Graph ≠ authority · derived indexes only
            {isDemo ? " · demo isolated from LIVE_API" : " · LIVE_API read-only"}
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
