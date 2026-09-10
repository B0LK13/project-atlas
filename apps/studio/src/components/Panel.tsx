import type { ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";

export function Panel({
  eyebrow,
  title,
  meta,
  children,
  className = "",
  action,
}: {
  eyebrow?: string;
  title: string;
  meta?: ReactNode;
  children: ReactNode;
  className?: string;
  action?: { label: string; onClick: () => void };
}) {
  return (
    <section className={`panel ${className}`}>
      <header className="panel-header">
        <div>
          {eyebrow ? <p className="panel-eyebrow">{eyebrow}</p> : null}
          <h2>{title}</h2>
        </div>
        <div className="panel-header-end">
          {meta}
          {action ? (
            <button className="icon-button quiet" onClick={action.onClick} aria-label={action.label}>
              <ArrowUpRight size={15} aria-hidden="true" />
            </button>
          ) : null}
        </div>
      </header>
      <div className="panel-body">{children}</div>
    </section>
  );
}
