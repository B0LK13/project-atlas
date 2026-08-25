import { ProdShell } from "../../components/ProdShell";
import { useRevocations } from "../../hooks/useRevocations";

/**
 * Receipt revocations micro-lens — AS-CODER-ALPHA-REVOCATIONS-READ-001.
 * LIVE_API operational index only; demo never fabricates revocation rows.
 */
export default function RevocationsPage() {
  const { view, error, loading, dataSource } = useRevocations();
  const isDemo = dataSource === "demo_stub" || view?.demo_isolated === true;
  const available = view?.available === true;
  const rollup = view?.status ?? "UNKNOWN";
  const rows = view?.revocations ?? [];

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">
            Production · Revocations · AS-CODER-ALPHA-REVOCATIONS-READ-001
          </p>
          <h1>Receipt revocations</h1>
          <p className="lede">
            Read-only operational revocation index. Missing evidence stays
            unknown; recorded rows are not project authority, owner capability,
            or AUTHENTIC_PILOT.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">empty≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? (
          <p className="banner warn">Revocations read failed: {error}</p>
        ) : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB — isolated sample data · not a live revocation index
          </p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Revocation rollup">
          <h2>Rollup</h2>
          <p className="flags">
            <span className="chip">available={String(available)}</span>
            <span className="chip">status={rollup}</span>
            <span className="chip">reason={view?.reason_code ?? "UNKNOWN"}</span>
            <span className="chip">
              rows={String(view?.revocation_count ?? 0)}
            </span>
          </p>
          {!available ? (
            <p className="banner warn">
              {view?.reason ?? "unknown — no receipt-revocation index on disk"}
            </p>
          ) : (
            <p>
              Receipt revocations are <strong>{rollup.toLowerCase()}</strong>.
              That is not a claim the vault is current, validated, or
              authoritative.
            </p>
          )}
        </section>

        <section className="panel" aria-label="Revocation inventory">
          <h2>Revocations</h2>
          {rows.length === 0 ? (
            <p className="banner warn">
              unknown — no revocation rows (demo stub or empty index)
            </p>
          ) : (
            <ul className="theme-hub">
              {rows.map((row) => (
                <li key={row.unit_key ?? `${row.project_id}/${row.event_id}`}>
                  <strong>{row.unit_key ?? "UNKNOWN"}</strong>
                  <span>
                    {row.status ?? "unknown"} · {row.reason ?? "unknown"}
                    {row.receipt_path ? ` · ${row.receipt_path}` : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Revocation boundaries">
          <h2>Boundaries</h2>
          <p className="banner warn">
            UI ≠ canonical — browser state is never vault truth.
          </p>
          <p className="banner warn">
            UNKNOWN ≠ HEALTHY — a missing index never looks ready.
          </p>
          <p className="banner warn">
            EMPTY ≠ HEALTHY — a zero-row index is not a green estate.
          </p>
          <p className="disclaimer">
            Read-only lens · no revoke/write · RECEIPT REVOCATION ≠ owner
            authority
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
