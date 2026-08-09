import { NavLink } from "react-router-dom";

const PROD_LINKS = [
  { to: "/", label: "Home", end: true },
  { to: "/projects", label: "Projects" },
  { to: "/knowledge", label: "Knowledge" },
  { to: "/graph", label: "Graph" },
  { to: "/ops", label: "Ops" },
  { to: "/command-center", label: "Command Center" },
  { to: "/mission-control", label: "Mission Control" },
] as const;

/** Production shell chrome — read-only; UI≠canonical. */
export function ProdNav() {
  return (
    <nav className="prod-nav" aria-label="Production shell">
      {PROD_LINKS.map((link) => (
        <NavLink key={link.to} to={link.to} end={"end" in link ? link.end : false}>
          {link.label}
        </NavLink>
      ))}
      <span className="lab-badge">AS-WEB-ACCEPT · UI≠canonical · read-only</span>
    </nav>
  );
}
