import { ProdShell } from "../../components/ProdShell";
import { useIncrementalConnect } from "../../hooks/useIncrementalConnect";

/**
 * Incremental-connect micro-lens — AS-CODER-ALPHA-INCREMENTAL-CONNECT-READ-001.
 * LIVE_API operational receipt only; demo never fabricates a no-change skip.
 */
export default function IncrementalConnectPage() {
  const { view, error, loading, dataSource } = useIncrementalConnect();
  const isDemo = dataSource === "demo_stub" || view?.demo_isolated === true;
  const available = view?.available === true;
  const rollup = view?.status ?? "UNKNOWN";
  const disposition = view?.disposition ?? "unknown";
  const counters = view?.counters ?? {};

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">
            Production · Incremental connect · AS-CODER-ALPHA-INCREMENTAL-CONNECT-READ-001
          </p>
          <h1>Incremental connect</h1>
          <p className="lede">
            Read-only operational reconnect receipt. A missing receipt stays
            unknown; a recorded no-change skip is not validate, owner
            capability, or AUTHENTIC_PILOT.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">skip≠authority</span>
            <span className="chip">absent≠skip</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? (
          <p className="banner warn">Incremental-connect read failed: {error}</p>
        ) : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB — isolated sample data · not a live incremental-connect receipt
          </p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Incremental-connect rollup">
          <h2>Rollup</h2>
          <p className="flags">
            <span className="chip">available={String(available)}</span>
            <span className="chip">status={rollup}</span>
            <span className="chip">disposition={disposition}</span>
            <span className="chip">reason={view?.reason_code ?? "UNKNOWN"}</span>
          </p>
          {!available ? (
            <p className="banner warn">
              {view?.reason ?? "unknown — no incremental-connect receipt on disk"}
            </p>
          ) : (
            <p>
              Last reconnect disposition is <strong>{disposition}</strong>.
              That is operational history, not a claim the vault is current,
              validated, or authoritative.
            </p>
          )}
        </section>

        <section className="panel" aria-label="Incremental-connect counters">
          <h2>Counters</h2>
          <p className="flags">
            <span className="chip">
              inspected={String(counters.files_inspected ?? 0)}
            </span>
            <span className="chip">
              ingest={String(counters.ingest_invocations ?? 0)}
            </span>
            <span className="chip">
              discover={String(counters.discover_invocations ?? 0)}
            </span>
            <span className="chip">
              writes={String(counters.physical_writes ?? 0)}
            </span>
          </p>
        </section>

        <section className="panel" aria-label="Incremental-connect boundaries">
          <h2>Boundaries</h2>
          <p className="banner warn">
            UI ≠ canonical — browser state is never vault truth.
          </p>
          <p className="banner warn">
            UNKNOWN ≠ HEALTHY — a missing receipt never looks like a skip.
          </p>
          <p className="banner warn">
            SKIP ≠ VALIDATE — no-change skip is not owner authority.
          </p>
          <p className="disclaimer">
            Read-only lens · no connect/write · INCREMENTAL SKIP ≠ owner
            authority
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
