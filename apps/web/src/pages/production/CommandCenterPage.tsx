import { NavLink, useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { ReadStatusPanel } from "../../components/ReadStatusPanel";
import { useReadStatus } from "../../hooks/useReadStatus";

const MODES = [
  {
    id: "overview",
    label: "Overview",
    blurb: "Combined read-status / estate summary (sample or live adapter).",
  },
  {
    id: "projects",
    label: "Projects",
    blurb: "Project inventory lens — navigate to /projects for the list view.",
  },
  {
    id: "ops",
    label: "Ops",
    blurb: "OBS health consume — unknown when snapshot absent (never fabricate healthy).",
  },
  {
    id: "impact",
    label: "Impact",
    blurb: "Optional derived impact graph consume only — Graph ≠ authority.",
  },
] as const;

type ModeId = (typeof MODES)[number]["id"];

function isMode(value: string | null): value is ModeId {
  return MODES.some((mode) => mode.id === value);
}

/**
 * Command Center — presentation lenses only; never vault writers.
 * WEB APPLICATION ACCEPTED is not claimed by this surface.
 */
export default function CommandCenterPage() {
  const [params, setParams] = useSearchParams();
  const raw = params.get("mode");
  const mode: ModeId = isMode(raw) ? raw : "overview";
  const { status, error, loading } = useReadStatus();
  const active = MODES.find((item) => item.id === mode) ?? MODES[0];

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Command Center · AS-WEB-003</p>
          <h1>Command Center</h1>
          <p className="lede">
            Named read lenses for operators. Modes switch presentation only —
            UI is not canonical; graph is not authority; unknown is never healthy.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">graph_authority=false</span>
            <span className="chip">WEB ACCEPTED=not claimed</span>
          </p>
        </header>

        <nav className="mode-switcher" aria-label="Command Center modes">
          {MODES.map((item) => (
            <button
              key={item.id}
              type="button"
              className={item.id === mode ? "mode active" : "mode"}
              onClick={() => setParams({ mode: item.id })}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <section className="panel" aria-label={`Mode ${active.label}`}>
          <h2>{active.label}</h2>
          <p className="disclaimer">{active.blurb}</p>

          {mode === "overview" ? (
            <>
              {error ? (
                <p className="banner warn">Read status unavailable: {error}</p>
              ) : null}
              {loading ? <p className="banner">Loading read status…</p> : null}
              {status ? <ReadStatusPanel status={status} /> : null}
              {!loading && !status && !error ? (
                <p className="banner warn">unknown — no read-status evidence</p>
              ) : null}
            </>
          ) : null}

          {mode === "projects" ? (
            <p>
              Open the <NavLink to="/projects">Projects</NavLink> production
              route for inventory. Missing inventory → unknown, not invented.
            </p>
          ) : null}

          {mode === "ops" ? (
            <p>
              Open <NavLink to="/ops">Ops health</NavLink>. Absent OBS snapshot
              must render unknown / unavailable — never fabricated healthy.
            </p>
          ) : null}

          {mode === "impact" ? (
            <p className="disclaimer">
              Impact lens is derived-only consume (AS-J-005 when present). This
              shell does not elevate graph edges to authority winners.
            </p>
          ) : null}
        </section>
      </main>
    </ProdShell>
  );
}
