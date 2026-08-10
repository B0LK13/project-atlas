import { ProdShell } from "../../components/ProdShell";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * Ops Health micro-lens — AS-WEB-OPS-HEALTH-001.
 * Read-only operational and receipt evidence; never a vault writer or authority.
 * UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy.
 */
export default function OpsHealthPage() {
  const { status, error, loading, dataSource } = useReadStatus();
  const health = status?.health;
  const available = health?.available === true;
  const rollup = available ? health?.rollup ?? "unknown" : "unknown";
  const isDemo = dataSource === "demo_stub" || status?.demo_isolated === true;

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">
            Production · Ops Health · AS-WEB-OPS-HEALTH-001
          </p>
          <h1>Ops health</h1>
          <p className="lede">
            Read-only operational health and receipt evidence. Absent snapshots
            render unknown; the browser never fabricates health, receipts, or
            PILOT estate rows.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">graph_authority=false</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Health read failed: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">DEMO STUB — isolated sample data · not live vault</p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Health rollup">
          <h2>Rollup</h2>
          <p className="flags">
            <span className="chip">available={String(available)}</span>
            <span className="chip">rollup={rollup}</span>
            <span className="chip">read_plane={status?.read_plane ?? "unknown"}</span>
          </p>
          {!available ? (
            <p className="banner warn">unknown — OBS / health unavailable</p>
          ) : (
            <p>
              Operational rollup <strong>{rollup}</strong> (ops plane only — not
              project authority).
            </p>
          )}
          <p className="disclaimer">
            Unknown ≠ healthy · UI ≠ canonical · operational rollup ≠ project
            authority
            {isDemo ? " · demo isolated" : ""}
          </p>
        </section>

        <section className="panel" aria-label="Receipt evidence">
          <h2>Receipt evidence</h2>
          <p className="banner warn">
            unknown — no live receipt adapter is wired in the static shell.
            Receipt rows and completion claims are not inferred from UI state.
          </p>
          <p className="flags">
            <span className="chip">receipt_source=unavailable</span>
            <span className="chip">receipt_rows=unknown</span>
            <span className="chip">read_only=true</span>
          </p>
        </section>

        <section className="panel" aria-label="Ops Health boundaries">
          <h2>Boundaries</h2>
          <p className="banner warn">UI ≠ canonical — browser state is never vault truth.</p>
          <p className="banner warn">Graph ≠ authority — derived edges never pick winners.</p>
          <p className="banner warn">No PILOT estate rows are invented.</p>
          <p className="disclaimer">
            Read-only lens · no vault mutation APIs · WEB APPLICATION ACCEPTED = YES · UI ≠ canonical
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
