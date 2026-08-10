import { ProdShell } from "../../components/ProdShell";
import { useLiveMission } from "../../hooks/useLiveMissionWorkspace";

/**
 * Mission Control lens — AS-WEB-MISSION-001 / LIVE deepen.
 * LIVE_API preferred; demo stub isolated; never invents PILOT estate rows.
 */
export default function MissionControlPage() {
  const { view, error, loading, dataSource } = useLiveMission();
  const isDemo = dataSource === "demo_stub" || view?.demo_isolated === true;

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Mission Control · AS-WEB-MISSION-001</p>
          <h1>Mission Control</h1>
          <p className="lede">
            Operator mission lens. LIVE_API composition preferred; demo fallback
            isolated. Never invents PILOT estate rows or elevates UI to vault truth.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">graph_authority=false</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Mission unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">DEMO STUB — isolated sample · not live vault · not PILOT</p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — composed read projection</p>
        ) : null}

        <section className="panel" aria-label="Mission Control banners">
          <h2>Invariants</h2>
          <p className="banner warn">UI ≠ canonical — browser state is never vault truth.</p>
          <p className="banner warn">Graph ≠ authority — derived edges never pick winners.</p>
          <p className="banner warn">Unknown ≠ healthy — absent evidence stays unknown.</p>
        </section>

        <section className="panel" aria-label="Mission Control board">
          <h2>Mission board</h2>
          {!loading && !view ? (
            <p className="banner warn">unknown — mission view unavailable</p>
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
                <dt>Board available</dt>
                <dd>{String(view.mission_board_available ?? false)}</dd>
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
      </main>
    </ProdShell>
  );
}
