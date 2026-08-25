import { ProdShell } from "../../components/ProdShell";
import { useLiveSnapshot } from "../../hooks/useLiveSnapshot";

/**
 * LIVE_API facade snapshot — not a backup bundle.
 * UI ≠ canonical. Graph ≠ authority. Unknown ≠ healthy.
 */
export default function SnapshotPage() {
  const { snapshot, error, loading, dataSource } = useLiveSnapshot();
  const isDemo = dataSource === "demo_stub";
  const liveReady = dataSource === "live_api";
  const projects = snapshot?.projects ?? [];
  const knowledge = snapshot?.knowledge ?? [];
  const graph = snapshot?.graph;

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Snapshot · AS-CODER-ALPHA-SNAPSHOT-MCP-001</p>
          <h1>Facade snapshot</h1>
          <p className="lede">
            Read-only LIVE_API facade snapshot of health, projects, knowledge,
            and graph counts. This is not an Atlas backup/restore bundle and
            does not grant owner authority.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">graph_authority=false</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">facade≠backup</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Snapshot unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            the live facade snapshot (not vault truth)
          </p>
        ) : liveReady ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Facade snapshot">
          <h2>Projection</h2>
          {liveReady && !snapshot ? (
            <p className="banner warn">unknown — no facade snapshot available</p>
          ) : snapshot ? (
            <dl className="grid">
              <div>
                <dt>Projects</dt>
                <dd>{String(projects.length)}</dd>
              </div>
              <div>
                <dt>Knowledge rows</dt>
                <dd>{String(knowledge.length)}</dd>
              </div>
              <div>
                <dt>Graph available</dt>
                <dd>{String(graph?.available ?? "unknown")}</dd>
              </div>
              <div>
                <dt>Graph nodes</dt>
                <dd>{String(graph?.node_count ?? "unknown")}</dd>
              </div>
            </dl>
          ) : !liveReady && !snapshot ? (
            <p className="lede">
              {error
                ? "Unavailable — not an empty snapshot catalog."
                : isDemo
                  ? "Demo stub isolated — not an empty snapshot catalog."
                  : "Waiting for live facade snapshot."}
            </p>
          ) : null}
          <p className="disclaimer">
            Facade snapshot ≠ backup bundle · ≠ authority · UI ≠ canonical
            {isDemo ? " · demo isolated from LIVE_API" : " · LIVE_API read-only"}
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
