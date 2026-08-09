import { Link } from "react-router-dom";
import { LabShell } from "../components/LabShell";
import { ReadStatusPanel } from "../components/ReadStatusPanel";
import { useReadStatus } from "../hooks/useReadStatus";

const THEMES = [
  {
    to: "/design-lab/ledger-desk",
    title: "A · Ledger Desk",
    blurb: "Warm paper field, serif display, monospace status chips.",
  },
  {
    to: "/design-lab/signal-rack",
    title: "B · Signal Rack",
    blurb: "Dark charcoal rails, teal lamps — unknown never green.",
  },
  {
    to: "/design-lab/cartograph-quiet",
    title: "C · Cartograph Quiet",
    blurb: "Map-grid field, waypoints, legend key for health.",
  },
  {
    to: "/design-lab/terminal-honest",
    title: "D · Terminal Honest",
    blurb: "Monochrome terminal; ui_canonical=false always visible.",
  },
] as const;

/** Foundation hub — Theme A lean + links into design-lab prototypes. */
export default function HomePage() {
  const { status, error, loading } = useReadStatus();

  return (
    <LabShell theme="ledger-desk" className="theme-ledger">
      <main className="shell">
        <header className="hero">
          <p className="eyebrow">Project Atlas · AS-WEB-002</p>
          <h1>Atlas</h1>
          <p className="lede">
            Read-first vault status shell and design-lab prototypes. UI is not
            canonical; graph is not authority; unknown is never healthy.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">graph_authority=false</span>
            <span className="chip">unknown≠healthy</span>
          </p>
        </header>

        {error ? <p className="banner warn">Read status unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading read status…</p> : null}
        {status ? <ReadStatusPanel status={status} /> : null}

        <section className="panel" aria-label="Design lab themes">
          <h2>Design lab</h2>
          <p className="disclaimer">
            Four prototype themes from AS-WEB-001-DESIGN-LAB — not production UI
            acceptance.
          </p>
          <ul className="theme-hub">
            {THEMES.map((theme) => (
              <li key={theme.to}>
                <Link to={theme.to}>
                  <strong>{theme.title}</strong>
                  <span>{theme.blurb}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </main>
    </LabShell>
  );
}
