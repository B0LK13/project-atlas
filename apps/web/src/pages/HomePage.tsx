import { Link } from "react-router-dom";
import { ProdShell } from "../components/ProdShell";
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

const PROD = [
  { to: "/projects", title: "Projects", blurb: "Read-only inventory lens." },
  { to: "/ops", title: "Ops health", blurb: "OBS/sample consume — unknown ≠ healthy." },
  {
    to: "/ops-events",
    title: "Ops events",
    blurb: "AS-OBS-002 stream read — empty ≠ healthy; events ≠ authority.",
  },
  {
    to: "/command-center",
    title: "Command Center",
    blurb: "Mode switcher: overview · projects · ops · impact.",
  },
  {
    to: "/mission-control",
    title: "Mission Control",
    blurb: "AS-WEB-MISSION-001 stub — UI≠canonical; ACCEPTED=YES.",
  },
  {
    to: "/workspace",
    title: "Workspace",
    blurb: "AS-WEB-WORKSPACE-001 stub — UI≠canonical; ACCEPTED=YES.",
  },
  {
    to: "/roadmap",
    title: "Roadmap",
    blurb: "Living Project Roadmap V1 — derived; ROADMAP≠canonical.",
  },
  {
    to: "/intelligence",
    title: "Intelligence",
    blurb: "Read-only derived intelligence — DERIVED≠authority.",
  },
] as const;

/** Production home hub + design-lab links. WEB ACCEPTED not claimed. */
export default function HomePage() {
  const { status, error, loading, dataSource, livePreferred, liveError } = useReadStatus();
  // Honest fallback signal: LIVE_API was preferred but unreachable, so the demo
  // stub below is a fallback (never silently labelled LIVE). See AS-WEB-LIVE-001.
  const liveFellBackToDemo = livePreferred && dataSource === "demo_stub" && liveError !== null;

  return (
    <ProdShell className="theme-ledger">
      <main className="shell">
        <header className="hero">
          <p className="eyebrow">Project Atlas · AS-WEB-003</p>
          <h1>Atlas</h1>
          <p className="lede">
            Production read shell and design-lab prototypes. UI is not canonical;
            graph is not authority; unknown is never healthy. Web application
            acceptance is not claimed by this package.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">graph_authority=false</span>
            <span className="chip">unknown≠healthy</span>
          </p>
        </header>

        {error ? <p className="banner warn">Read status unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading read status…</p> : null}
        {liveFellBackToDemo ? (
          <p className="banner warn">
            LIVE_API not reachable ({liveError}) — showing isolated DEMO stub, not
            live vault. Start “atlas live api-serve” and open this app at
            http://127.0.0.1:5173 (not localhost) so the API CORS origin matches.
          </p>
        ) : null}
        {status ? <ReadStatusPanel status={status} /> : null}

        <section className="panel" aria-label="Production shell">
          <h2>Production shell</h2>
          <p className="disclaimer">
            Operator surfaces from ADR-010 — still read-only; not WEB ACCEPTED.
          </p>
          <ul className="theme-hub">
            {PROD.map((item) => (
              <li key={item.to}>
                <Link to={item.to}>
                  <strong>{item.title}</strong>
                  <span>{item.blurb}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <section className="panel" aria-label="Design lab themes">
          <h2>Design lab</h2>
          <p className="disclaimer">
            Four prototype themes from AS-WEB-002 — retained; not production
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
    </ProdShell>
  );
}
