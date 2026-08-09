import { ProdShell } from "../../components/ProdShell";

/**
 * Workspace lens — AS-WEB-WORKSPACE-001.
 * Read-only stub UI; never vault writers; WEB APPLICATION ACCEPTED not claimed.
 * UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy.
 */
export default function WorkspacePage() {
  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Workspace · AS-WEB-WORKSPACE-001</p>
          <h1>Workspace</h1>
          <p className="lede">
            Operator workspace lens stub. Presentation only — does not compile
            claims, invent PILOT estate rows, or elevate UI state to vault truth.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">graph_authority=false</span>
            <span className="chip">unknown≠healthy</span>
          </p>
        </header>

        <section className="panel" aria-label="Workspace banners">
          <h2>Invariants</h2>
          <p className="banner warn">UI ≠ canonical — browser state is never vault truth.</p>
          <p className="banner warn">Graph ≠ authority — derived edges never pick winners.</p>
          <p className="banner warn">Unknown ≠ healthy — absent evidence stays unknown.</p>
        </section>

        <section className="panel" aria-label="Workspace stub">
          <h2>Workspace board</h2>
          <p className="banner warn">
            unknown — no live workspace adapter in the static shell; sample stub at{" "}
            <code>/sample-workspace.json</code> is flags-only (no PILOT estate
            rows).
          </p>
          <p className="disclaimer">
            UI ≠ canonical · Graph ≠ authority · Unknown ≠ healthy · WEB
            APPLICATION ACCEPTED = NO
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
