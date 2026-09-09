import { useEffect, useMemo, useRef, useState } from "react";
import {
  Bot,
  Boxes,
  BrainCircuit,
  Clock3,
  FolderKanban,
  GitBranch,
  Radar,
  Search,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import type { ScreenId } from "../types";

const commands: Array<{ id: ScreenId; label: string; detail: string; icon: typeof Radar; keywords: string }> = [
  { id: "mission-control", label: "Mission Control", detail: "Current objective and attention", icon: Radar, keywords: "home objective attention" },
  { id: "projects", label: "Projects", detail: "Project portfolio", icon: FolderKanban, keywords: "portfolio workspace" },
  { id: "agents", label: "Agents", detail: "Entities, lanes and boundaries", icon: Bot, keywords: "models workers ownership" },
  { id: "work-graph", label: "DAG / Work Graph", detail: "Frontier and dependencies", icon: Boxes, keywords: "dag graph nodes runnable" },
  { id: "repository", label: "Repository / Changes", detail: "Objects, branch and diff", icon: GitBranch, keywords: "git head tree base files" },
  { id: "verification", label: "CI & Verification", detail: "Evidence pipeline", icon: ShieldCheck, keywords: "tests adv iv merge seal" },
  { id: "knowledge", label: "Knowledge", detail: "Claims, sources and conflicts", icon: BrainCircuit, keywords: "truth evidence decisions" },
  { id: "chronicle", label: "Activity / Chronicle", detail: "What happened while away", icon: Clock3, keywords: "events history timeline" },
  { id: "settings", label: "Settings / Environment", detail: "Read source and display", icon: Settings, keywords: "theme density linux source" },
  { id: "design-lab", label: "Design Lab", detail: "Three Mission Control directions", icon: Search, keywords: "prototype orbit workbench twin" },
];

export function CommandPalette({
  open,
  onClose,
  onNavigate,
}: {
  open: boolean;
  onClose: () => void;
  onNavigate: (id: ScreenId) => void;
}) {
  const [query, setQuery] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const dialog = useRef<HTMLElement>(null);
  const results = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return commands;
    return commands.filter((command) => `${command.label} ${command.detail} ${command.keywords}`.toLowerCase().includes(needle));
  }, [query]);

  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setQuery("");
    const frame = requestAnimationFrame(() => input.current?.focus());
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); onClose(); }
      if (event.key === "Tab") {
        const controls = Array.from(dialog.current?.querySelectorAll<HTMLElement>("input, button:not(:disabled)") ?? []);
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => { cancelAnimationFrame(frame); document.removeEventListener("keydown", onKey); previous?.focus(); };
  }, [onClose, open]);

  if (!open) return null;
  return (
    <div className="palette-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
      <section ref={dialog} className="command-palette" role="dialog" aria-modal="true" aria-labelledby="palette-title">
        <header>
          <Search size={17} aria-hidden="true" />
          <input
            ref={input}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && results[0]) {
                // Closing restores focus to the trigger; suppress Enter's default click.
                event.preventDefault();
                onNavigate(results[0].id);
                onClose();
              }
            }}
            placeholder="Navigate Atlas Studio…"
            aria-label="Search read-only Studio destinations"
          />
          <button onClick={onClose} aria-label="Close command palette"><X size={16} /></button>
        </header>
        <div className="palette-context">
          <span id="palette-title">READ-ONLY COMMAND SURFACE</span>
          <span>Navigation only · no execution</span>
        </div>
        <ul>
          {results.map((command) => {
            const Icon = command.icon;
            return (
              <li key={command.id}>
                <button onClick={() => { onNavigate(command.id); onClose(); }}>
                  <span className="palette-icon"><Icon size={16} aria-hidden="true" /></span>
                  <span><strong>{command.label}</strong><small>{command.detail}</small></span>
                  <kbd>↵</kbd>
                </button>
              </li>
            );
          })}
          {!results.length ? <li className="palette-empty">No readable destination matches “{query}”.</li> : null}
        </ul>
        <footer><span><kbd>Esc</kbd> close</span><span>Actions requiring authority are intentionally absent.</span></footer>
      </section>
    </div>
  );
}
