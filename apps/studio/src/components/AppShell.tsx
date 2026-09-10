import { useEffect, useRef, type ReactNode } from "react";
import {
  Bell,
  Bot,
  Boxes,
  BrainCircuit,
  ChevronDown,
  Clock3,
  Command,
  FolderKanban,
  GitBranch,
  LayoutGrid,
  Menu,
  Moon,
  Radar,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  Sun,
  X,
} from "lucide-react";
import type { DensityMode, ScreenId, StudioEnvelope, ThemeMode } from "../types";

const nav: Array<{ id: ScreenId; label: string; icon: typeof Radar; section: "primary" | "project" | "system" }> = [
  { id: "mission-control", label: "Mission Control", icon: Radar, section: "primary" },
  { id: "projects", label: "Projects", icon: FolderKanban, section: "primary" },
  { id: "agents", label: "Agents", icon: Bot, section: "primary" },
  { id: "work-graph", label: "DAG / Work Graph", icon: Boxes, section: "project" },
  { id: "repository", label: "Repository", icon: GitBranch, section: "project" },
  { id: "verification", label: "CI & Verification", icon: ShieldCheck, section: "project" },
  { id: "knowledge", label: "Knowledge", icon: BrainCircuit, section: "project" },
  { id: "chronicle", label: "Chronicle", icon: Clock3, section: "project" },
  { id: "design-lab", label: "Design Lab", icon: LayoutGrid, section: "system" },
  { id: "settings", label: "Environment", icon: Settings, section: "system" },
];

function AtlasMark() {
  return (
    <span className="atlas-mark" aria-hidden="true">
      <i /><i /><i />
    </span>
  );
}

export function AppShell({
  active,
  onNavigate,
  data,
  loading,
  error,
  theme,
  density,
  onTheme,
  onDensity,
  onRefresh,
  onPalette,
  mobileOpen,
  onMobileOpen,
  children,
}: {
  active: ScreenId;
  onNavigate: (id: ScreenId) => void;
  data: StudioEnvelope;
  loading: boolean;
  error: string | null;
  theme: ThemeMode;
  density: DensityMode;
  onTheme: () => void;
  onDensity: () => void;
  onRefresh: () => void;
  onPalette: () => void;
  mobileOpen: boolean;
  onMobileOpen: (open: boolean) => void;
  children: ReactNode;
}) {
  const navigation = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!mobileOpen) return;
    const previous = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    navigation.current?.querySelector<HTMLButtonElement>(".mobile-close")?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.preventDefault(); onMobileOpen(false); }
      if (event.key === "Tab") {
        const controls = Array.from(navigation.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [])
          .filter(button => button.getClientRects().length > 0);
        const first = controls[0], last = controls.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); previous?.focus(); };
  }, [mobileOpen, onMobileOpen]);
  const sourceClass = data.source.kind === "DESIGN_PREVIEW" ? "source-fixture" : data.source.current ? "source-live" : "source-degraded";
  return (
    <div className="studio-shell">
      <a className="skip-link" href="#studio-main" onClick={(event) => { event.preventDefault(); document.getElementById("studio-main")?.focus(); }}>
        Skip to project view
      </a>
      <aside ref={navigation} className={`side-rail ${mobileOpen ? "is-open" : ""}`} aria-label="Atlas Studio navigation">
        <div className="brand-row">
          <AtlasMark />
          <div><strong>ATLAS</strong><span>STUDIO / 0.1</span></div>
          <button className="mobile-close" onClick={() => onMobileOpen(false)} aria-label="Close navigation"><X size={17} /></button>
        </div>
        <button className="project-switcher" onClick={() => { onNavigate("projects"); onMobileOpen(false); }}>
          <span className="project-coordinate">A/01</span>
          <span><strong>Project workspace</strong><small>{data.projection.repository || "Unavailable"}</small></span>
          <ChevronDown size={14} aria-hidden="true" />
        </button>
        {(["primary", "project", "system"] as const).map((section) => (
          <nav key={section} aria-label={`${section} navigation`}>
            <p>{section === "primary" ? "COMMAND" : section === "project" ? "PROJECT PLANE" : "STUDIO"}</p>
            {nav.filter((item) => item.section === section).map((item) => {
              const Icon = item.icon;
              return (
                <button key={item.id} className={active === item.id ? "is-active" : ""} onClick={() => { onNavigate(item.id); onMobileOpen(false); }} aria-current={active === item.id ? "page" : undefined}>
                  <Icon size={16} strokeWidth={1.8} aria-hidden="true" />
                  <span>{item.label}</span>
                </button>
              );
            })}
          </nav>
        ))}
        <div className="authority-footer">
          <ShieldCheck size={15} aria-hidden="true" />
          <span><strong>READ-ONLY LANE</strong><small>Studio grants no mutation</small></span>
        </div>
      </aside>
      <div className="studio-frame">
        <header className="top-bar">
          <button className="mobile-menu" onClick={() => onMobileOpen(true)} aria-label="Open navigation" aria-expanded={mobileOpen}><Menu size={18} /></button>
          <button className="search-trigger" onClick={onPalette}>
            <Search size={15} aria-hidden="true" />
            <span>Navigate Studio screens…</span>
            <kbd><Command size={11} aria-hidden="true" /> K</kbd>
          </button>
          <div className="top-actions">
            <button className="icon-button" onClick={onRefresh} aria-label="Refresh read-only projection" disabled={loading}>
              <RefreshCw className={loading ? "is-spinning" : ""} size={16} />
            </button>
            <button className="icon-button" onClick={onDensity} aria-label={`Density ${density}; switch density`}><LayoutGrid size={16} /></button>
            <button className="icon-button" onClick={onTheme} aria-label={`Theme ${theme}; switch theme`}>{theme === "dark" ? <Moon size={16} /> : <Sun size={16} />}</button>
            <button className="icon-button notification" aria-label="Inspect projection attention" onClick={() => onNavigate("mission-control")}><Bell size={16} /></button>
          </div>
        </header>
        <div className={`source-ribbon ${sourceClass}`} role="status" aria-live="polite">
          <span className="source-glyph">{data.source.kind === "DESIGN_PREVIEW" ? "◇" : data.source.current ? "●" : "◌"}</span>
          <strong>{data.source.label}</strong>
          <span>{data.source.detail}</span>
          {error && error !== data.source.detail ? <code>{error}</code> : null}
        </div>
        <main id="studio-main" tabIndex={-1} className="studio-main">
          {children}
        </main>
      </div>
      {mobileOpen ? <button className="rail-scrim" onClick={() => onMobileOpen(false)} aria-label="Close navigation overlay" /> : null}
    </div>
  );
}
