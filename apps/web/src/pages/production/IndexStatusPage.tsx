import { ProdShell } from "../../components/ProdShell";
import { useIndexStatus } from "../../hooks/useIndexStatus";

/**
 * Index status micro-lens — AS-CODER-ALPHA-INDEX-STATUS-001.
 * LIVE_API lexical indexes only; demo never fabricates retrieval readiness.
 */
export default function IndexStatusPage() {
  const { view, error, loading, dataSource } = useIndexStatus();
  const isDemo = dataSource === "demo_stub" || view?.demo_isolated === true;
  const available = view?.available === true;
  const rollup = view?.status ?? "UNKNOWN";
  const indexes = view?.indexes ?? [];

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">
            Production · Index status · AS-CODER-ALPHA-INDEX-STATUS-001
          </p>
          <h1>Index status</h1>
          <p className="lede">
            Read-only lexical index readiness. Missing evidence stays unknown;
            a recorded index is not freshness, validate-pass, or query
            authority.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">presence≠validate</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Index status read failed: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB — isolated sample data · not a live index inventory
          </p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Index rollup">
          <h2>Rollup</h2>
          <p className="flags">
            <span className="chip">available={String(available)}</span>
            <span className="chip">status={rollup}</span>
            <span className="chip">reason={view?.reason_code ?? "UNKNOWN"}</span>
            <span className="chip">
              required={String(view?.required_present ?? 0)}/
              {String(view?.required_total ?? 0)}
            </span>
          </p>
          {!available ? (
            <p className="banner warn">
              {view?.reason ?? "unknown — no lexical indexes on disk"}
            </p>
          ) : (
            <p>
              Lexical indexes are <strong>recorded</strong>. That is not a
              claim the vault is current, validated, or authoritative.
            </p>
          )}
        </section>

        <section className="panel" aria-label="Index inventory">
          <h2>Indexes</h2>
          {indexes.length === 0 ? (
            <p className="banner warn">unknown — no index rows (demo stub or empty vault)</p>
          ) : (
            <ul className="theme-hub">
              {indexes.map((row) => (
                <li key={row.name ?? row.relative_path}>
                  <strong>{row.name ?? "UNKNOWN"}</strong>
                  <span>
                    {row.presence ?? "unknown"} · {row.role ?? "unknown"}
                    {row.id_count == null ? "" : ` · ids=${row.id_count}`}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Index status boundaries">
          <h2>Boundaries</h2>
          <p className="banner warn">UI ≠ canonical — browser state is never vault truth.</p>
          <p className="banner warn">UNKNOWN ≠ HEALTHY — missing indexes never look ready.</p>
          <p className="banner warn">PRESENCE ≠ VALIDATE — recorded files are not a Core pass.</p>
          <p className="disclaimer">
            Read-only lens · no vault mutation · INDEX_STATUS ≠ owner authority
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
