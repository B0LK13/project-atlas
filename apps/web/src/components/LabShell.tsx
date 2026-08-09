import type { ReactNode } from "react";
import { useEffect } from "react";
import { LabNav } from "./LabNav";

export type ThemeId =
  | "ledger-desk"
  | "signal-rack"
  | "cartograph-quiet"
  | "terminal-honest";

interface LabShellProps {
  theme: ThemeId;
  className?: string;
  children: ReactNode;
}

/** Applies shared tokens via data-theme; sample UI only. */
export function LabShell({ theme, className, children }: LabShellProps) {
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    return () => {
      document.documentElement.removeAttribute("data-theme");
    };
  }, [theme]);

  return (
    <div data-theme={theme} className={className}>
      <LabNav />
      {children}
    </div>
  );
}
