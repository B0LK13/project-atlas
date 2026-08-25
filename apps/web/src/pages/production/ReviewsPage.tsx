import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveReviews } from "../../hooks/useLiveReviews";
import { useReadStatus } from "../../hooks/useReadStatus";

/**
 * AS-CODER-ALPHA-REVIEW-MCP-001 web lens — read-only pending reviews.
 * UI ≠ canonical; REVIEW ≠ decide; UNKNOWN ≠ healthy.
 * Project is explicit ?project= only. No silent fixture default.
 */
export default function ReviewsPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam && projectParam.trim() ? projectParam.trim() : null;
  const { inventory, error, loading, dataSource } = useLiveReviews(projectId);
  const isDemo = dataSource === "demo_stub";
  const pending = inventory?.pending_reviews ?? [];
  const decided = inventory?.human_decisions ?? [];
  const inventoryProject =
    typeof inventory?.project_id === "string" ? inventory.project_id.trim() : "";
  const projectMismatch = Boolean(
    inventory && projectId && inventoryProject && inventoryProject !== projectId,
  );

  function onSelectProject(next: string) {
    const nextParams = new URLSearchParams(params);
    if (next) {
      nextParams.set("project", next);
    } else {
      nextParams.delete("project");
    }
    setParams(nextParams, { replace: true });
  }

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Human review</p>
          <h1>Reviews</h1>
          <p className="lede">
            Read-only pending-review and recorded human-decision inventory for{" "}
            <code>{projectId ?? "the vault"}</code>. This page does not accept
            or reject reviews. Not canonical. Not authority. Empty is UNKNOWN,
            not a healthy zero.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">review≠authority</span>
            <span className="chip">unknown≠healthy</span>
            <span className="chip">decide_or_promote=false</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="review-project">
            Focus project
          </label>
          <select
            id="review-project"
            value={projectId ?? ""}
            onChange={(event) => onSelectProject(event.target.value)}
            style={{ display: "block", marginTop: "0.5rem", maxWidth: "24rem" }}
          >
            <option value="">all vault reviews</option>
            {projects.map((project) => (
              <option
                key={project.project_id ?? project.path}
                value={project.project_id ?? ""}
              >
                {project.project_id ?? "unnamed"}
              </option>
            ))}
          </select>
        </section>

        {error ? <p className="banner warn">Reviews unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to
            read live review queues (not invented)
          </p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — review project does not match selected project
          </p>
        ) : null}
        {!loading &&
        !error &&
        !isDemo &&
        !projectMismatch &&
        pending.length === 0 &&
        decided.length === 0 ? (
          <p className="banner warn">
            UNKNOWN — no pending reviews or recorded human decisions. Empty is
            not a healthy zero.
          </p>
        ) : null}

        {!projectMismatch && pending.length > 0 ? (
          <section className="panel" aria-label="Pending reviews">
            <h2>Pending</h2>
            <p className="lede">count={inventory?.pending_count ?? 0}</p>
            <ul>
              {pending.map((row) => (
                <li key={`${row.project_id}-${row.review_id}`}>
                  <strong>{row.review_id ?? "UNKNOWN"}</strong>
                  {" · "}
                  {row.project_id ?? "UNKNOWN"}
                  {" · "}
                  {row.status ?? "pending"}
                  <div className="lede">{row.reason ?? "UNKNOWN"}</div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {!projectMismatch && decided.length > 0 ? (
          <section className="panel" aria-label="Human decisions">
            <h2>Recorded human decisions</h2>
            <p className="lede">
              count={inventory?.human_decision_count ?? 0} · not authority
            </p>
            <ul>
              {decided.map((row) => (
                <li key={`${row.project_id}-${row.review_id}-decided`}>
                  <strong>{row.review_id ?? "UNKNOWN"}</strong>
                  {" · "}
                  {row.decision ?? "UNKNOWN"}
                  <div className="lede">{row.reason ?? "UNKNOWN"}</div>
                </li>
              ))}
            </ul>
          </section>
        ) : null}
      </main>
    </ProdShell>
  );
}
