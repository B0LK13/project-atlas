import { LabShell } from "../../components/LabShell";
import { ReadStatusPanel } from "../../components/ReadStatusPanel";
import { useReadStatus } from "../../hooks/useReadStatus";

/** Theme A — Ledger Desk (design-lab prototype). */
export default function LedgerDeskPage() {
  const { status, error, loading } = useReadStatus();

  return (
    <LabShell theme="ledger-desk" className="theme-ledger">
      <main className="shell">
        <header className="hero">
          <p className="eyebrow">Design lab · Theme A</p>
          <h1>Ledger Desk</h1>
          <p className="lede">
            Warm paper blotter over an ops ledger — never a truth editor.
            Single-column read status; monospace chips only.
          </p>
          <p className="flags">
            <span className="chip">sample</span>
            <span className="chip">ui≠canonical</span>
          </p>
        </header>
        {error ? <p className="banner warn">Read status unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading read status…</p> : null}
        {status ? <ReadStatusPanel status={status} /> : null}
      </main>
    </LabShell>
  );
}
