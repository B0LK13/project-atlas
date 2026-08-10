import { ProdShell } from "../../components/ProdShell";
import { useLiveWorkspace } from "../../hooks/useLiveMissionWorkspace";

/**
 * Workspace lens — AS-WEB-WORKSPACE-001 / LIVE deepen + UX polish.
 * LIVE_API preferred; demo stub isolated; never invents PILOT estate rows.
 */
export default function WorkspacePage() {
  const { view, error, loading, dataSource } = useLiveWorkspace();
  const isDemo = dataSource === "demo_stub" || view?.demo_isolated === true;
  const surfaces =
    view && typeof view.surfaces === "object" && view.surfaces !== null
      ? (view.surfaces as Record<string, unknown>)
      : {};

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Workspace · AS-WEB-WORKSPACE-001</p>
          <h1>Workspace</h1>
          <p className="lede">
            Operator workspace lens. LIVE_API composition preferred; demo fallback
            isolated. Never invents PILOT estate rows or elevates UI to vault truth.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">graph_authority=false</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">authentic_pilot=false</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Workspace unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">DEMO STUB — isolated sample · not live vault · not PILOT</p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — composed read projection</p>
        ) : null}

        <section className="panel" aria-label="Workspace banners">
          <h2>Invariants</h2>
          <p className="banner warn">UI ≠ canonical — browser state is never vault truth.</p>
          <p className="banner warn">Graph ≠ authority — derived edges never pick winners.</p>
          <p className="banner warn">Unknown ≠ healthy — absent evidence stays unknown.</p>
        </section>

        <section className="panel" aria-label="Workspace board">
          <h2>Workspace board</h2>
          {!loading && !view ? (
            <p className="banner warn">unknown — workspace view unavailable</p>
          ) : null}
          {view?.empty_projects === true ? (
            <p className="banner warn">unknown — no project rows (honest empty)</p>
          ) : null}
          {view?.empty_knowledge === true ? (
            <p className="banner warn">unknown — no knowledge rows (honest empty)</p>
          ) : null}
          {view ? (
            <dl className="grid">
              <div>
                <dt>Rollup</dt>
                <dd>{String(view.rollup ?? "unknown")}</dd>
              </div>
              <div>
                <dt>Project count</dt>
                <dd>{String(view.project_count ?? "unknown")}</dd>
              </div>
              <div>
                <dt>Knowledge count</dt>
                <dd>{String(view.knowledge_count ?? "unknown")}</dd>
              </div>
              <div>
                <dt>Board available</dt>
                <dd>{String(view.workspace_board_available ?? false)}</dd>
              </div>
              <div>
                <dt>PILOT estate rows</dt>
                <dd>{Array.isArray(view.pilot_estate_rows) ? view.pilot_estate_rows.length : 0}</dd>
              </div>
              <div>
                <dt>Authentic pilot</dt>
                <dd>{String(view.authentic_pilot ?? false)}</dd>
              </div>
            </dl>
          ) : null}
          <p className="disclaimer">
            UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy · no PILOT invent
            · WEB APPLICATION ACCEPTED = YES
            {isDemo ? " · demo isolated" : " · LIVE_API read-only"}
          </p>
        </section>

        <section className="panel" aria-label="Workspace surface presence">
          <h2>Surface presence</h2>
          <p className="flags">
            {Object.keys(surfaces).length === 0 ? (
              <span className="chip">surfaces=unknown</span>
            ) : (
              Object.entries(surfaces).map(([key, value]) => (
                <span className="chip" key={key}>
                  {key}={String(value)}
                </span>
              ))
            )}
          </p>
          <p className="disclaimer">
            Presence flags only · missing surface ≠ healthy · not release certification
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
