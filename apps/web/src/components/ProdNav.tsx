import { NavLink, useSearchParams } from "react-router-dom";

const PROD_LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/projects", label: "Projects" },
  { to: "/discovery", label: "Discovery" },
  { to: "/knowledge", label: "Knowledge" },
  { to: "/intelligence", label: "Intelligence" },
  { to: "/context", label: "Context" },
  { to: "/ask", label: "Ask" },
  { to: "/time-machine", label: "Time Machine" },
  { to: "/roadmap", label: "Roadmap" },
  { to: "/graph", label: "Graph" },
  { to: "/ops", label: "Ops" },
  { to: "/revocations", label: "Revocations" },
  { to: "/command-center", label: "Command Center" },
  { to: "/mission-control", label: "Mission Control" },
  { to: "/workspace", label: "Workspace" },
] as const;

/** Project-scoped lenses. Preserve ?project= only — never from=/to=. */
const PROJECT_AWARE_PATHS = new Set([
  "/knowledge",
  "/intelligence",
  "/context",
  "/ask",
  "/time-machine",
  "/roadmap",
  "/workspace",
]);

/** Build a nav href. Copies project=P only; does not invent a default project. */
export function projectAwareHref(path: string, project: string | null): string {
  if (!project || !PROJECT_AWARE_PATHS.has(path)) {
    return path;
  }
  return `${path}?project=${encodeURIComponent(project)}`;
}

/** Production shell chrome — read-only; UI≠canonical. */
export function ProdNav() {
  const [params] = useSearchParams();
  const project = params.get("project");

  return (
    <nav className="prod-nav" aria-label="Production shell">
      {PROD_LINKS.map((link) => (
        <NavLink
          key={link.to}
          to={projectAwareHref(link.to, project)}
          end={"end" in link ? link.end : false}
        >
          {link.label}
        </NavLink>
      ))}
      <span className="lab-badge">AS-WEB-ACCEPT · UI≠canonical · read-only</span>
    </nav>
  );
}
