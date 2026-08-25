import { Link } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLivePortfolioIndex } from "../../hooks/useLivePortfolioIndex";

/**
 * AS-CODER-ALPHA-PORTFOLIO-INDEX-001 — vault-scoped portfolio index.
 * Composes existing /v1/projects (via read-status) + /v1/portfolio-state.
 * UI ≠ canonical. PORTFOLIO ≠ authority. Does not invent projects.
 */

function textOrUnknown(value: unknown): string {
  if (typeof value === "string" && value.trim()) {
    return value;
  }
  return "UNKNOWN";
}

export default function PortfolioIndexPage() {
  const { index, error, loading, dataSource } = useLivePortfolioIndex();
  const isDemo = dataSource === "demo_stub";
  const rows = index.rows;
  const state = (index.portfolio?.state ?? null) as Record<string, unknown> | null;
  const entries = Array.isArray(state?.entries)
    ? (state?.entries as Array<Record<string, unknown>>)
    : [];
  const attention = Array.isArray(index.portfolio?.attention)
    ? (index.portfolio?.attention as Array<Record<string, unknown>>)
    : [];

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">
            Production · Portfolio index · AS-CODER-ALPHA-PORTFOLIO-INDEX-001
          </p>
          <h1>Portfolio state</h1>
          <p className="lede">
            Vault-scoped read of existing portfolio state. This page enumerates
            projects from read-status, then calls{" "}
            <code>/v1/portfolio-state</code> with those explicit ids. It does
            not invent a <code>/v1/portfolio</code> protocol, does not call
            empty-arg portfolio-state, and does not write Layer B. Missing
            evidence stays UNKNOWN. Not <code>atlas.portfolio.state.read</code>{" "}
            MCP. Not authority.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">portfolio≠authority</span>
            <span className="chip">mcp≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">owner_capability_granted=false</span>
            <span className="chip">zero_arg_vault_scope=true</span>
            <span className="chip">empty_arg_portfolio_state=false</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? (
          <p className="banner warn">Portfolio index read failed: {error}</p>
        ) : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB — isolated sample inventory · portfolio not fabricated
          </p>
        ) : dataSource === "live_api" ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Vault-scoped portfolio cards">
          <h2>Projects in scope</h2>
          <p className="flags">
            <span className="chip">project_count={String(index.project_count)}</span>
            <span className="chip">
              included={String(index.included_ids.length)}
            </span>
            <span className="chip">
              available={String(index.available)}
            </span>
          </p>
          {rows.length === 0 && !loading ? (
            <p className="banner warn">UNKNOWN — no project rows in read-status</p>
          ) : (
            <ul className="theme-hub">
              {rows.map((row) => (
                <li key={row.project_id}>
                  <Link
                    to={`/intelligence?project=${encodeURIComponent(row.project_id)}&view=portfolio`}
                  >
                    <strong>{row.project_id}</strong>
                    <span>
                      {row.included ? "included in portfolio scope" : "skipped invalid id"}
                    </span>
                  </Link>
                  <p className="disclaimer">
                    {row.path ? row.path : "path UNKNOWN"}
                    {" · "}
                    <Link to={`/knowledge?project=${encodeURIComponent(row.project_id)}`}>
                      Knowledge
                    </Link>
                    {" · "}
                    <Link
                      to={`/intelligence?project=${encodeURIComponent(row.project_id)}`}
                    >
                      Intelligence
                    </Link>
                  </p>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="panel" aria-label="Derived portfolio aggregate">
          <h2>Derived aggregate</h2>
          <p className="lede">
            Cross-project derived state only. No numeric priority score.
            PORTFOLIO ≠ authority.
          </p>
          {!index.available || isDemo ? (
            <p className="banner warn">
              UNKNOWN — portfolio body not fabricated
              {isDemo ? " · demo isolated" : ""}
            </p>
          ) : entries.length === 0 ? (
            <p className="banner warn">UNKNOWN — no portfolio entries</p>
          ) : (
            <ul className="theme-hub">
              {entries.map((entry) => {
                const pid = textOrUnknown(entry.project_id);
                const derived = (entry.state ?? null) as Record<string, unknown> | null;
                const status = textOrUnknown(derived?.status ?? derived?.lifecycle);
                return (
                  <li key={pid}>
                    <strong>{pid}</strong>
                    <span>derived status: {status}</span>
                  </li>
                );
              })}
            </ul>
          )}
          {attention.length > 0 && index.available && !isDemo ? (
            <p className="disclaimer">
              Attention signals: {String(attention.length)} · risk≠fact
            </p>
          ) : null}
          <p className="disclaimer">
            UI ≠ canonical · PORTFOLIO ≠ authority · MCP ≠ authority
            {isDemo ? " · demo isolated" : " · LIVE_API read-only"}
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
