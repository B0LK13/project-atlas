import { ProdShell } from "../../components/ProdShell";
import { useLiveActions } from "../../hooks/useLiveActions";

/**
 * LIVE_API web action ledger — reconstructable GET projection.
 * UI ≠ canonical. Ledger ≠ Truth Core. GET ≠ POST.
 */
export default function ActionsPage() {
  const { ledger, error, loading, dataSource } = useLiveActions();
  const isDemo = dataSource === "demo_stub";
  const liveReady = dataSource === "live_api";
  const transactions = ledger?.transactions ?? [];

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">
            Production · Actions · AS-CODER-ALPHA-ACTIONS-LEDGER-MCP-001
          </p>
          <h1>Action ledger</h1>
          <p className="lede">
            Read-only reconstructable web action ledger. This page never posts
            actions, never writes Layer B, and is not Truth Core authority.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">ledger≠truth-core</span>
            <span className="chip">get≠post</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Ledger unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            the live action ledger (not vault truth)
          </p>
        ) : liveReady ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Action ledger">
          <h2>Projection</h2>
          {liveReady && !ledger ? (
            <p className="banner warn">unknown — no action ledger available</p>
          ) : ledger ? (
            <dl className="grid">
              <div>
                <dt>Transactions</dt>
                <dd>{String(transactions.length)}</dd>
              </div>
              <div>
                <dt>Ledger package</dt>
                <dd>{String(ledger.package_id ?? "unknown")}</dd>
              </div>
            </dl>
          ) : !liveReady && !ledger ? (
            <p className="lede">
              {error
                ? "Unavailable — not an empty healthy ledger."
                : isDemo
                  ? "Demo stub isolated — not an empty healthy ledger."
                  : "Waiting for live action ledger."}
            </p>
          ) : null}
          {liveReady && transactions.length === 0 ? (
            <p className="disclaimer">Empty ledger is valid — not healthy, not PILOT.</p>
          ) : null}
          {transactions.length > 0 ? (
            <ul>
              {transactions.slice(0, 12).map((row, index) => (
                <li key={String(row.action_id ?? index)}>
                  {String(row.action_type ?? row.action_id ?? "unknown-action")}
                </li>
              ))}
            </ul>
          ) : null}
          <p className="disclaimer">
            Ledger ≠ Truth Core · GET ≠ POST · UI ≠ canonical
            {isDemo ? " · demo isolated from LIVE_API" : " · LIVE_API read-only"}
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
