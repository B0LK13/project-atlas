import { LabShell } from "../../components/LabShell";
import { useReadStatus } from "../../hooks/useReadStatus";

/** Theme D — Terminal Honest (design-lab prototype). */
export default function TerminalHonestPage() {
  const { status, error, loading } = useReadStatus();

  const termBody = status
    ? [
        `{`,
        `  "ui_canonical": ${String(status.ui_canonical)},`,
        `  "graph_authority": ${String(status.graph_authority)},`,
        `  "unknown_equals_healthy": ${String(status.unknown_equals_healthy)},`,
        `  "read_plane": "${status.read_plane}",`,
        `  "health": {`,
        `    "rollup": "${status.health.rollup}",`,
        `    "available": ${String(status.health.available)},`,
        `    "source": "${status.health.source}"`,
        `  },`,
        `  "vault_id": ${status.vault_id ? `"${status.vault_id}"` : "null"},`,
        `  "projects": ${status.projects.length}`,
        `}`,
      ].join("\n")
    : null;

  return (
    <LabShell theme="terminal-honest" className="theme-terminal">
      <main className="shell">
        <header className="hero">
          <p className="eyebrow">design-lab / theme-d</p>
          <h1>$ atlas design-lab --theme terminal-honest</h1>
          <p className="lede">
            Near-monochrome terminal aesthetic. Operator honesty over marketing
            polish. Explicit JSON-ish fields always visible.
          </p>
        </header>

        {error ? <p className="banner warn"># error: {error}</p> : null}
        {loading ? <p className="banner"># loading sample-read-status…</p> : null}

        {termBody ? (
          <pre className="term-block" aria-label="Terminal read status">
            <span className="prompt"># sample stub — not vault truth{"\n"}</span>
            {termBody}
          </pre>
        ) : null}
      </main>
    </LabShell>
  );
}
