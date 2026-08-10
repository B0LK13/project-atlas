import { ProdShell } from "../../components/ProdShell";
import { useLiveKnowledge } from "../../hooks/useLiveKnowledge";

/**
 * Knowledge answers lens — LIVE_API first; demo-isolated empty fallback.
 * Never compiles claims; UI ≠ canonical.
 */
export default function KnowledgePage() {
  const { knowledge, error, loading, dataSource } = useLiveKnowledge();
  const isDemo = dataSource === "demo_stub";

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Knowledge</p>
          <h1>Knowledge</h1>
          <p className="lede">
            Read-only answer inventory. LIVE_API preferred; demo fallback stays
            empty and isolated — answers are never invented in the browser.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">graph_authority=false</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">
              data_source={dataSource ?? "unknown"}
            </span>
          </p>
        </header>

        {error ? <p className="banner warn">Knowledge unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}

        <section className="panel" aria-label="Knowledge answers">
          <h2>Answer inventory</h2>
          {isDemo ? (
            <p className="banner warn">
              DEMO STUB isolated — no live knowledge rows; not vault truth
            </p>
          ) : null}
          {!loading && knowledge.length === 0 ? (
            <p className="banner warn">unknown — no knowledge rows</p>
          ) : (
            <ul className="theme-hub">
              {knowledge.map((row, index) => (
                <li key={String(row.answer_id ?? row.subject ?? index)}>
                  <strong>{String(row.subject ?? row.title ?? row.answer_id ?? "row")}</strong>
                  <span>{String(row.summary ?? "")}</span>
                </li>
              ))}
            </ul>
          )}
          <p className="disclaimer">
            UI ≠ canonical · Graph ≠ authority · knowledge_compiler never imported
            {isDemo ? " · demo isolated from LIVE_API" : " · LIVE_API read-only"}
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
