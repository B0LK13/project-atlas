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
      <ProdNav />
      {children}
    </div>
  );
}
