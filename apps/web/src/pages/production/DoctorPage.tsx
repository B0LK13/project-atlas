import { ProdShell } from "../../components/ProdShell";
import { useLiveDoctor } from "../../hooks/useLiveDoctor";

/**
 * AS-CODER-ALPHA-DOCTOR-MCP-001 web lens — read-only doctor diagnostics.
 * UI ≠ canonical; DOCTOR ≠ authority; UNKNOWN ≠ healthy.
 */
export default function DoctorPage() {
  const { report, error, loading, dataSource } = useLiveDoctor();
  const isDemo = dataSource === "demo_stub";
  const checks = report?.checks ?? [];
  const rollup = report?.rollup ?? "unknown";

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Environment doctor</p>
          <h1>Doctor</h1>
          <p className="lede">
            Read-only <code>atlas doctor</code> projection for this vault.
            Operational signals only. This page does not repair, write, or
            grant owner gates. Not canonical. Not authority. Unknown is never
            healthy.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">doctor≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">owner_gate_grant=false</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Doctor unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to
            read live doctor checks (not invented)
          </p>
        ) : null}
        {!loading && !error && !isDemo && checks.length === 0 ? (
          <p className="banner warn">
            UNKNOWN — no doctor checks. Empty is not a healthy zero.
          </p>
        ) : null}

        {!isDemo && checks.length > 0 ? (
          <section className="panel" aria-label="Doctor checks">
            <h2>Checks</h2>
            <p className="lede">
              rollup={rollup} · count={report?.check_count ?? 0} · ok=
              {String(report?.ok ?? false)}
            </p>
            <ul>
              {checks.map((check) => (
                <li key={check.name ?? check.detail}>
                  <strong>{check.status ?? "unknown"}</strong>
                  {" · "}
                  {check.name ?? "UNKNOWN"}
                  <div className="lede">{check.detail ?? "UNKNOWN"}</div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </main>
    </ProdShell>
  );
}
