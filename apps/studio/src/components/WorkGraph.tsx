import { useEffect, useMemo, useRef, useState } from "react";
import { Crosshair, Minus, Plus, RotateCcw } from "lucide-react";
import type { PointerEvent as ReactPointerEvent } from "react";
import type { WorkEdgePreview, WorkNodePreview } from "../types";
import { TruthBadge } from "./StatusLanguage";
import { EmptyState } from "./EmptyState";

const CANVAS_WIDTH = 850;
const CANVAS_HEIGHT = 470;

export function WorkGraph({
  nodes,
  edges,
  compact = false,
}: {
  nodes: WorkNodePreview[];
  edges: WorkEdgePreview[];
  compact?: boolean;
}) {
  const [zoom, setZoom] = useState(compact ? 0.83 : 1);
  const [offset, setOffset] = useState({ x: compact ? -30 : 0, y: 0 });
  const viewport = useRef<HTMLDivElement>(null);
  const [fit, setFit] = useState(1);
  useEffect(() => {
    const element = viewport.current;
    if (!element) return;
    const observer = new ResizeObserver(() => {
      const scale = Math.min(1, element.clientWidth / CANVAS_WIDTH, element.clientHeight / CANVAS_HEIGHT);
      setFit(scale); setZoom(scale); setOffset({ x: 0, y: 0 });
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [nodes.length]);
  const [selected, setSelected] = useState<string | null>(nodes.find((node) => node.current)?.id ?? null);
  const drag = useRef<{ startX: number; startY: number; originX: number; originY: number } | null>(null);
  const byId = useMemo(() => new Map(nodes.map((node) => [node.id, node])), [nodes]);
  const selectedNode = nodes.find((node) => node.id === selected);

  if (!nodes.length) {
    return <EmptyState title="Work graph unavailable" detail="No typed graph nodes were present in this projection." />;
  }

  const clampZoom = (value: number) => Math.min(1.45, Math.max(0.2, value));
  const reset = () => {
    setZoom(fit);
    setOffset({ x: 0, y: 0 });
  };
  const focusCurrent = () => {
    const current = nodes.find((node) => node.current);
    if (!current) return;
    setSelected(current.id);
    setZoom(1.12);
    setOffset({ x: CANVAS_WIDTH / 2 - current.x * 1.12, y: CANVAS_HEIGHT / 2 - current.y * 1.12 });
  };
  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if ((event.target as HTMLElement).closest("button")) return;
    drag.current = { startX: event.clientX, startY: event.clientY, originX: offset.x, originY: offset.y };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!drag.current) return;
    setOffset({
      x: drag.current.originX + event.clientX - drag.current.startX,
      y: drag.current.originY + event.clientY - drag.current.startY,
    });
  };
  const stopDrag = () => {
    drag.current = null;
  };

  return (
    <div className={`work-graph ${compact ? "graph-compact" : ""}`}>
      <div className="graph-toolbar" aria-label="Graph controls">
        <button onClick={() => setZoom((value) => clampZoom(value - 0.12))} aria-label="Zoom out">
          <Minus size={14} aria-hidden="true" />
        </button>
        <span aria-live="polite">{Math.round(zoom * 100)}%</span>
        <button onClick={() => setZoom((value) => clampZoom(value + 0.12))} aria-label="Zoom in">
          <Plus size={14} aria-hidden="true" />
        </button>
        <button onClick={focusCurrent} disabled={!nodes.some(node => node.current)} aria-label="Focus current frontier">
          <Crosshair size={14} aria-hidden="true" />
        </button>
        <button onClick={reset} aria-label="Reset graph view">
          <RotateCcw size={14} aria-hidden="true" />
        </button>
      </div>
      <div
        ref={viewport}
        className="graph-viewport"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={stopDrag}
        onPointerCancel={stopDrag}
        onWheel={(event) => {
          event.preventDefault();
          setZoom((value) => clampZoom(value + (event.deltaY > 0 ? -0.08 : 0.08)));
        }}
      >
        <div
          className="graph-canvas"
          style={{
            width: CANVAS_WIDTH,
            height: CANVAS_HEIGHT,
            transform: `translate(${offset.x}px, ${offset.y}px) scale(${zoom})`,
          }}
        >
          <svg viewBox={`0 0 ${CANVAS_WIDTH} ${CANVAS_HEIGHT}`} aria-hidden="true">
            <defs>
              <marker id="graph-arrow" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M 0 0 L 8 4 L 0 8 z" />
              </marker>
            </defs>
            {edges.map((edge) => {
              const from = byId.get(edge.from);
              const to = byId.get(edge.to);
              if (!from || !to) return null;
              const bend = Math.abs(to.x - from.x) * 0.42;
              return (
                <path
                  key={`${edge.from}-${edge.to}`}
                  className={`graph-edge edge-${edge.state}`}
                  d={`M ${from.x + 58} ${from.y + 26} C ${from.x + 58 + bend} ${from.y + 26}, ${to.x - bend} ${to.y + 26}, ${to.x} ${to.y + 26}`}
                  markerEnd="url(#graph-arrow)"
                />
              );
            })}
          </svg>
          {nodes.map((node) => (
            <button
              key={node.id}
              className={`graph-node node-${node.state} ${node.current ? "is-current" : ""} ${selected === node.id ? "is-selected" : ""}`}
              style={{ left: node.x, top: node.y }}
              onClick={() => setSelected(node.id)}
              aria-pressed={selected === node.id}
              aria-label={`${node.label}, ${node.state}, ${node.truth}`}
            >
              <span className="graph-node-eyebrow">{node.eyebrow}</span>
              <strong>{node.label}</strong>
              <span className="graph-node-state">{node.state}</span>
            </button>
          ))}
        </div>
      </div>
      {selectedNode ? (
        <div className="graph-inspector" aria-live="polite">
          <div>
            <span className="graph-inspector-kicker">Selected coordinate</span>
            <strong>{selectedNode.label}</strong>
          </div>
          <TruthBadge state={selectedNode.truth} compact />
          <p>{selectedNode.detail}</p>
          <span>{selectedNode.owner ? `Owner · ${selectedNode.owner}` : "UNOWNED"}</span>
        </div>
      ) : null}
    </div>
  );
}
