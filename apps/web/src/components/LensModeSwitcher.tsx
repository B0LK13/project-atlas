/**
 * AS-2.1-WEB-MISSION-WORKSPACE-UX — visible LIVE / DEMO / FIXTURE modes.
 * LIVE-first default; presentation only; never vault writers; no PILOT invent.
 */

export const LENS_MODES = [
  {
    id: "live",
    label: "LIVE",
    blurb: "Prefer LIVE_API composition. Unavailable stays unknown — never invent.",
  },
  {
    id: "demo",
    label: "DEMO",
    blurb: "Isolated demo stub. Not live vault. Not PILOT estate.",
  },
  {
    id: "fixture",
    label: "FIXTURE",
    blurb: "Deterministic fixture sample for gates. Flags only; no PILOT invent.",
  },
] as const;

export type LensModeId = (typeof LENS_MODES)[number]["id"];

export function isLensMode(value: string | null | undefined): value is LensModeId {
  return LENS_MODES.some((mode) => mode.id === value);
}

export function resolveLensMode(value: string | null | undefined): LensModeId {
  return isLensMode(value) ? value : "live";
}

interface LensModeSwitcherProps {
  mode: LensModeId;
  onChange: (mode: LensModeId) => void;
  ariaLabel?: string;
}

export function LensModeSwitcher({
  mode,
  onChange,
  ariaLabel = "Lens data modes",
}: LensModeSwitcherProps) {
  return (
    <nav className="mode-switcher" aria-label={ariaLabel}>
      {LENS_MODES.map((item) => (
        <button
          key={item.id}
          type="button"
          className={item.id === mode ? `mode active mode-${item.id}` : `mode mode-${item.id}`}
          aria-pressed={item.id === mode}
          title={item.blurb}
          onClick={() => onChange(item.id)}
        >
          {item.label}
        </button>
      ))}
    </nav>
  );
}
