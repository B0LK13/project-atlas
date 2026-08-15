import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { ProdShell } from "../../components/ProdShell";
import { useLiveBrief } from "../../hooks/useLiveBrief";
import { useReadStatus } from "../../hooks/useReadStatus";
import { renderAgentContextMarkdown } from "../../lib/agentContextMarkdown";

/**
 * AS-CODER-ALPHA-CONTEXT-001 web paste pack.
 * Read-only live brief → markdown. Does not write atlas context files.
 * UI ≠ canonical. LENS ≠ authority.
 */
export default function ContextPage() {
  const [params, setParams] = useSearchParams();
  const { status, loading: statusLoading } = useReadStatus();
  const projects = status?.projects ?? [];
  const projectParam = params.get("project");
  const projectId =
    projectParam ??
    (projects.find((p) => p.project_id === "project-atlas")?.project_id ??
      projects[0]?.project_id ??
      null);
  const { brief, error, loading, dataSource } = useLiveBrief(projectId);
  const isDemo = dataSource === "demo_stub";
  const briefProject =
    typeof brief?.project_id === "string" ? brief.project_id.trim() : "";
  const selectedProject = projectId?.trim() ?? "";
  const projectMismatch = Boolean(
    brief && selectedProject && briefProject && briefProject !== selectedProject,
  );
  const markdown =
    brief && !projectMismatch
      ? renderAgentContextMarkdown(brief, selectedProject || undefined)
      : "";
  const [copyState, setCopyState] = useState<string | null>(null);

  function onSelectProject(next: string) {
    const nextParams = new URLSearchParams(params);
    if (next) {
      nextParams.set("project", next);
    } else {
      nextParams.delete("project");
    }
    setParams(nextParams, { replace: true });
    setCopyState(null);
  }

  async function onCopy(): Promise<void> {
    if (!markdown) {
      setCopyState("UNKNOWN — no live context to copy");
      return;
    }
    try {
      await navigator.clipboard.writeText(markdown);
      setCopyState("copied — still not authority");
    } catch (err: unknown) {
      setCopyState(err instanceof Error ? err.message : "copy failed");
    }
  }

  return (
    <ProdShell>
      <main id="main" className="shell" tabIndex={-1}>
        <header className="hero">
          <p className="eyebrow">Production · Agent context</p>
          <h1>Paste-ready agent context</h1>
          <p className="lede">
            Read-only markdown pack from the live project brief so the next
            agent does not need the project re-explained. This is not{" "}
            <code>atlas context</code> on-disk export. Not canonical. Not
            authority. UNKNOWN stays UNKNOWN.
          </p>
          <p className="flags" style={{ marginTop: "0.75rem" }}>
            <span className="chip">ui_canonical=false</span>
            <span className="chip">lens≠authority</span>
            <span className="chip">web_context≠atlas_context_file</span>
            <span className="chip">canonical_write=false</span>
            <span className="chip">derived≠authority</span>
            <span className="chip">data_source={dataSource ?? "unknown"}</span>
          </p>
        </header>

        <section className="panel" aria-label="Project selector">
          <h2>Project</h2>
          {statusLoading ? <p className="banner">Loading projects…</p> : null}
          <label className="lede" htmlFor="context-project">
            Focus project
          </label>
          <select
            id="context-project"
            value={projectId ?? ""}
            onChange={(event) => onSelectProject(event.target.value)}
            style={{ display: "block", marginTop: "0.5rem", maxWidth: "24rem" }}
          >
            {!projectId ? (
              <option value="">unknown — select a project</option>
            ) : null}
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

        {error ? <p className="banner warn">Context unavailable: {error}</p> : null}
        {loading ? <p className="banner">Loading…</p> : null}
        {isDemo ? (
          <p className="banner warn">
            DEMO STUB isolated — start <code>atlas live api-serve</code> to
            compile live context (not invented)
          </p>
        ) : null}
        {!loading && !error && !brief && dataSource === "live_api" ? (
          <p className="banner warn">UNKNOWN — no live brief projection</p>
        ) : null}
        {projectMismatch ? (
          <p className="banner warn">
            UNKNOWN — brief project does not match selected project
          </p>
        ) : null}

        {markdown ? (
          <section className="panel" aria-label="Paste pack">
            <h2>Markdown pack</h2>
            <button type="button" onClick={() => void onCopy()}>
              Copy for next agent (read-only)
            </button>
            {copyState ? <p className="lede">{copyState}</p> : null}
            <pre
              style={{
                marginTop: "1rem",
                whiteSpace: "pre-wrap",
                maxWidth: "48rem",
              }}
            >
              {markdown}
            </pre>
          </section>
        ) : null}

        <p className="disclaimer">
          WEB CONTEXT != ATLAS CONTEXT FILE / DERIVED != AUTHORITY /
          UI!=TRUTH / != AUTHORITY
          {isDemo ? " · demo isolated from LIVE_API" : " · LIVE_API read-only"}
        </p>
      </main>
    </ProdShell>
  );
}
