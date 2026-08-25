import { ProdShell } from "../../components/ProdShell";
import { useOpsEvents } from "../../hooks/useOpsEvents";

/**
 * Ops events micro-lens — AS-CODER-ALPHA-OPS-EVENTS-READ-001.
 * LIVE_API operational event stream only; demo never fabricates OPS-EVT rows.
 */
export default function OpsEventsPage() {
  const { view, error, loading, dataSource } = useOpsEvents();
  const isDemo = dataSource === "demo_stub" || view?.demo_isolated === true;
  const available = view?.available === true;
  const rollup = view?.status ?? "UNKNOWN";
  const events = view?.events ?? [];

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">
            Production · Ops events · AS-CODER-ALPHA-OPS-EVENTS-READ-001
          </p>
          <h1>Ops events</h1>
          <p className="lede">
            Read-only operational event stream. Missing evidence stays unknown;
            recorded OPS-EVT rows are not project authority, freshness, or
            AUTHENTIC_PILOT.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">empty≠healthy</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Ops events read failed: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB — isolated sample data · not a live ops-event stream
          </p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Ops event rollup">
          <h2>Rollup</h2>
          <p className="flags">
            <span className="chip">available={String(available)}</span>
            <span className="chip">status={rollup}</span>
            <span className="chip">reason={view?.reason_code ?? "UNKNOWN"}</span>
            <span className="chip">
              events={String(view?.event_count ?? 0)}
            </span>
          </p>
          {!available ? (
            <p className="banner warn">
              {view?.reason ?? "unknown — no ops event stream on disk"}
            </p>
          ) : (
            <p>
              Ops events are <strong>{rollup.toLowerCase()}</strong>. That is
              not a claim the vault is current, validated, or authoritative.
            </p>
          )}
        </section>

        <section className="panel" aria-label="Ops event inventory">
          <h2>Events</h2>
          {events.length === 0 ? (
            <p className="banner warn">
              unknown — no ops-event rows (demo stub or empty stream)
            </p>
          ) : (
            <ul className="theme-hub">
              {events.map((row) => (
                <li key={row.event_uid ?? `${row.event_id}-${row.sequence}`}>
                  <strong>{row.event_id ?? "UNKNOWN"}</strong>
                  <span>
                    seq={row.sequence ?? "unknown"} · {row.severity ?? "unknown"}
                    {row.authority_plane
                      ? ` · authority=${row.authority_plane}`
                      : ""}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Ops events boundaries">
          <h2>Boundaries</h2>
          <p className="banner warn">UI ≠ canonical — browser state is never vault truth.</p>
          <p className="banner warn">UNKNOWN ≠ HEALTHY — missing streams never look ready.</p>
          <p className="banner warn">EMPTY ≠ HEALTHY — a zero-event file is not a green estate.</p>
          <p className="disclaimer">
            Read-only lens · no emit/retain · OPS EVENT STREAM ≠ owner authority
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
