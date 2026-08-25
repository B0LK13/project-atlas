import { Link } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveBriefIndex } from "../../hooks/useLiveBriefIndex";

/**
 * AS-CODER-ALPHA-BRIEF-INDEX-WEB-001 — vault-scoped project brief cards.
 * Composes existing /v1/projects (via read-status) + /v1/brief.
 * UI ≠ canonical. BRIEF ≠ authority. Does not invent projects.
 */

function textOrUnknown(value: unknown): string {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  return "UNKNOWN";
}

export default function BriefIndexPage() {
  const { index, error, loading, dataSource } = useLiveBriefIndex();
  const isDemo = dataSource === "demo_stub";
  const rows = index.rows;

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">
            Production · Brief index · AS-CODER-ALPHA-BRIEF-INDEX-WEB-001
          </p>
          <h1>Project briefs</h1>
          <p className="lede">
            Vault-scoped read of existing project briefs. This page does not
            compile, connect, or write Layer B. Missing briefs stay UNKNOWN.
            Not <code>atlas.brief.read</code> MCP. Not authority.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">brief≠authority</span>
            <span className="chip">mcp≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">owner_capability_granted=false</span>
            <span className="chip">zero_arg_vault_scope=true</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Brief index read failed: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB — isolated sample inventory · briefs not fabricated
          </p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Vault-scoped brief cards">
          <h2>Briefs</h2>
          <p className="flags">
            <span className="chip">project_count={String(index.project_count)}</span>
            <span className="chip">
              available_rows={String(rows.filter((row) => row.available).length)}
            </span>
          </p>
          {rows.length === 0 && !loading ? (
            <p className="banner warn">UNKNOWN — no project rows in read-status</p>
          ) : (
            <ul className="theme-hub">
              {rows.map((row) => {
                const purpose = textOrUnknown(row.brief?.purpose);
                const state = textOrUnknown(row.brief?.current_state);
                const unknown = textOrUnknown(row.brief?.unknown_or_conflicting);
                const purposeUnknown = purpose.toUpperCase() === "UNKNOWN";
                return (
                  <li key={row.project_id}>
                    <Link to={`/knowledge?project=${encodeURIComponent(row.project_id)}`}>
                      <strong>{row.project_id}</strong>
                      <span>
                        {purposeUnknown ? "UNKNOWN purpose" : purpose} ·{" "}
                        {row.available ? "brief available" : "brief unavailable"}
                      </span>
                    </Link>
                    <p className={purposeUnknown ? "banner warn" : "lede"}>
                      State: {state}
                    </p>
                    <p className="disclaimer">
                      Unknown/conflict: {unknown}
                      {row.error ? ` · ${row.error}` : ""}
                      {row.path ? ` · ${row.path}` : ""}
                    </p>
                    <p className="disclaimer">
                      <Link to={`/knowledge?project=${encodeURIComponent(row.project_id)}`}>
                        Knowledge
                      </Link>
                      {" · "}
                      <Link to={`/context?project=${encodeURIComponent(row.project_id)}`}>
                        Context
                      </Link>
                      {" · "}
                      <Link to={`/roadmap?project=${encodeURIComponent(row.project_id)}`}>
                        Roadmap
                      </Link>
                    </p>
                  </li>
                );
              })}
            </ul>
          )}
          <p className="disclaimer">
            UI ≠ canonical · BRIEF ≠ authority · MCP ≠ authority
            {isDemo ? " · demo isolated" : " · LIVE_API read-only"}
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
