import { ProdShell } from "../../components/ProdShell";

/**
 * Knowledge answers lens — read-only consume of generated/answers stubs.
 * Never compiles claims; UI ≠ canonical.
 */
export default function KnowledgePage() {
  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Knowledge</p>
          <h1>Knowledge</h1>
          <p className="lede">
            Read-only answer inventory lens. Absent ``generated/answers`` stays
            unknown — answers are never invented in the browser.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">graph_authority=false</span>
            <span className="chip">unknown≠healthy</span>
          </p>
        </header>

        <section className="panel" aria-label="Knowledge answers">
          <h2>Answer inventory</h2>
          <p className="banner warn">
            unknown — no live answer adapter wired in the static shell; use{" "}
            <code>web_api.list_knowledge_answers(vault)</code> against a fixture
            vault for automated gates.
          </p>
          <p className="disclaimer">
            UI ≠ canonical · Graph ≠ authority · knowledge_compiler never imported
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
