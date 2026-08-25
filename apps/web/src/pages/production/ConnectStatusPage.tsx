import { ProdShell } from "../../components/ProdShell";
import { useConnectStatus } from "../../hooks/useConnectStatus";

/**
 * Connect status micro-lens — AS-CODER-ALPHA-CONNECT-STATUS-001.
 * LIVE_API connect receipts only; demo never fabricates a bound vault.
 */
export default function ConnectStatusPage() {
  const { view, error, loading, dataSource } = useConnectStatus();
  const isDemo = dataSource === "demo_stub" || view?.demo_isolated === true;
  const available = view?.available === true;
  const rollup = view?.status ?? "UNKNOWN";
  const connect = view?.connect_receipt;
  const incremental = view?.incremental_receipt;
  const projects = connect?.projects ?? [];

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">
            Production · Connect status · AS-CODER-ALPHA-CONNECT-STATUS-001
          </p>
          <h1>Connect status</h1>
          <p className="lede">
            Read-only last-connect receipt. Missing evidence stays unknown; a
            recorded receipt is not freshness, Truth Core, or owner authority.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">unknown≠fresh</span>
            <span className="chip">skip≠truth-core</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Connect status read failed: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB — isolated sample data · not a live connect receipt
          </p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Connect rollup">
          <h2>Rollup</h2>
          <p className="flags">
            <span className="chip">available={String(available)}</span>
            <span className="chip">status={rollup}</span>
            <span className="chip">reason={view?.reason_code ?? "UNKNOWN"}</span>
          </p>
          {!available ? (
            <p className="banner warn">
              {view?.reason ?? "unknown — no connect receipt on disk"}
            </p>
          ) : (
            <p>
              Connect receipt is <strong>recorded</strong>. That is not a claim
              the vault is current, compiled, or authoritative.
            </p>
          )}
        </section>

        <section className="panel" aria-label="Connect receipt">
          <h2>Connect receipt</h2>
          <ul className="theme-hub">
            <li>
              <strong>presence</strong>
              <span>{connect?.presence ?? "unknown"}</span>
            </li>
            <li>
              <strong>vault_id</strong>
              <span>{connect?.vault_id ?? "UNKNOWN"}</span>
            </li>
            <li>
              <strong>project_root</strong>
              <span>{connect?.project_root ?? "UNKNOWN"}</span>
            </li>
            <li>
              <strong>bound_project</strong>
              <span>{connect?.bound_project_id ?? "UNKNOWN"}</span>
            </li>
            <li>
              <strong>projects</strong>
              <span>{projects.length ? projects.join(", ") : "(none)"}</span>
            </li>
            <li>
              <strong>documents_ingested</strong>
              <span>{String(connect?.documents_ingested ?? "UNKNOWN")}</span>
            </li>
          </ul>
        </section>

        <section className="panel" aria-label="Incremental receipt">
          <h2>Incremental reconnect</h2>
          <p className="flags">
            <span className="chip">
              presence={incremental?.presence ?? "unknown"}
            </span>
            <span className="chip">
              disposition={incremental?.disposition ?? "UNKNOWN"}
            </span>
            <span className="chip">operational_only=true</span>
          </p>
          <p className="disclaimer">
            no_change_skip is operational only — it is not Truth Core compile
            and not AUTHENTIC_PILOT.
          </p>
        </section>

        <section className="panel" aria-label="Connect status boundaries">
          <h2>Boundaries</h2>
          <p className="banner warn">UI ≠ canonical — browser state is never vault truth.</p>
          <p className="banner warn">UNKNOWN ≠ FRESH — missing receipts never look current.</p>
          <p className="banner warn">SKIP ≠ TRUTH CORE — incremental skip is not compile authority.</p>
          <p className="disclaimer">
            Read-only lens · no vault mutation · CONNECT_STATUS ≠ owner authority
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
