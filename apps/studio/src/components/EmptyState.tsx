import { CircleDashed } from "lucide-react";

export function EmptyState({ title, detail, state = "UNKNOWN" }: { title: string; detail: string; state?: string }) {
  return (
    <div className="empty-state" role="status">
      <CircleDashed size={20} aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <p>{detail}</p>
        <span>{state}</span>
      </div>
    </div>
  );
}
