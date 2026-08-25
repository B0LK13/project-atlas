import { ProdShell } from "../../components/ProdShell";
import { useLiveValidate } from "../../hooks/useLiveValidate";

/**
 * LIVE_API vault validate — structural/provenance only.
 * UI ≠ canonical. OK ≠ healthy. Validate ≠ PILOT / authority.
 */
export default function ValidatePage() {
  const { report, error, loading, dataSource } = useLiveValidate();
  const isDemo = dataSource === "demo_stub";
  const liveReady = dataSource === "live_api";
  const errors = report?.errors ?? [];
  const findings = report?.findings ?? [];
  const ok = report?.ok === true;

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">
            Production · Validate · AS-CODER-ALPHA-VALIDATE-MCP-001
          </p>
          <h1>Vault validate</h1>
          <p className="lede">
            Read-only structural and provenance validation of the bound vault.
            A passing report is not healthy, not PILOT, and not authority.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">ok≠healthy</span>
            <span className="chip">ok≠pilot</span>
            <span className="chip">validate≠authority</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        {error ? <p className="banner warn">Validate unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to see
            the live validate report (not vault truth)
          </p>
        ) : liveReady ? (
          <p className="banner">LIVE_API — read-only vault projection</p>
        ) : null}

        <section className="panel" aria-label="Validate report">
          <h2>Projection</h2>
          {liveReady && !report ? (
            <p className="banner warn">unknown — no validate report available</p>
          ) : report ? (
            <dl className="grid">
              <div>
                <dt>ok</dt>
                <dd>{String(report.ok ?? "unknown")}</dd>
              </div>
              <div>
                <dt>Errors</dt>
                <dd>{String(report.error_count ?? errors.length)}</dd>
              </div>
              <div>
                <dt>Findings</dt>
                <dd>{String(report.finding_count ?? findings.length)}</dd>
              </div>
              <div>
                <dt>Markdown files</dt>
                <dd>{String(report.markdown_files ?? "unknown")}</dd>
              </div>
            </dl>
          ) : !liveReady && !report ? (
            <p className="lede">
              {error
                ? "Unavailable — not an empty passing validate report."
                : isDemo
                  ? "Demo stub isolated — not an empty passing validate report."
                  : "Waiting for live validate report."}
            </p>
          ) : null}
          {ok ? (
            <p className="disclaimer">
              ok=true is structural only — not healthy, not PILOT, not release.
            </p>
          ) : null}
          {errors.length > 0 ? (
            <ul>
              {errors.slice(0, 12).map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
          <p className="disclaimer">
            Validate ≠ authority · OK ≠ healthy · UI ≠ canonical
            {isDemo ? " · demo isolated from LIVE_API" : " · LIVE_API read-only"}
          </p>
        </section>
      </main>
    </ProdShell>
  );
}
