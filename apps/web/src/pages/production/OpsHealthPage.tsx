import { ProdShell } from "../../components/ProdShell";
import { useReadStatus } from "../../hooks/useReadStatus";

/** Production ops health — Unknown ≠ healthy. */
export default function OpsHealthPage() {
  const { status, error, loading } = useReadStatus();
  const health = status?.health;
  const available = health?.available === true;
  const rollup = available ? health?.rollup ?? "unknown" : "unknown";

  return (
    <ProdShell>
      <main className="shell">
        <header className="hero">
          <p className="eyebrow">Production · Ops</p>
          <h1>Ops health</h1>
          <p className="lede">
            Consume OBS / sample health only. Absent evidence renders unknown —
            never fabricated healthy.
          </p>
        </header>

        {error ? <p className="banner warn">Health read failed: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}

        <section className="panel" aria-label="Health rollup">
          <h2>Rollup</h2>
          <p className="flags">
            <span className="chip">available={String(available)}</span>
            <span className="chip">rollup={rollup}</span>
            <span className="chip">unknown≠healthy</span>
          </p>
          {!available ? (
            <p className="banner warn">unknown — OBS / sample health unavailable</p>
          ) : (
            <p>
              Operational rollup <strong>{rollup}</strong> (ops plane only — not
              project authority).
            </p>
          )}
          <p className="disclaimer">Graph ≠ authority · UI ≠ canonical</p>
        </section>
      </main>
    </ProdShell>
  );
}
