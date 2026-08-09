import type { ReactNode } from "react";
import { ProdNav } from "./ProdNav";

type Props = {
  children: ReactNode;
  className?: string;
};

/** Production chrome wrapper — Ledger Desk lean tokens; not vault authority. */
export function ProdShell({ children, className = "" }: Props) {
  return (
    <div className={`prod-shell theme-ledger ${className}`} data-theme="ledger-desk">
      <a className="skip-link" href="#main">
        Skip to main content
      </a>
      <ProdNav />
      {children}
    </div>
  );
}
