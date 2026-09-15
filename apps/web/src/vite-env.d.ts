/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_ATLAS_API_BASE?: string;
  /** Per-launch LIVE_API read Bearer from atlas-start (SEC-009); never commit. */
  readonly VITE_ATLAS_API_TOKEN?: string;
  readonly VITE_ATLAS_DEMO_ONLY?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
