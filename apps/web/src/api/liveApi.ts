/**
 * SEC-009 / E2E-003: LIVE_API client helper.
 * Prefer per-launch READ token via VITE_ATLAS_API_TOKEN (minted by api-serve,
 * propagated by scripts/windows/atlas-start.ps1). Never hardcode tokens,
 * never put tokens in URL/query, never disable auth.
 */

function envFlag(name: string): string | undefined {
  const env = (import.meta as ImportMeta & { env?: Record<string, string> }).env;
  return env?.[name];
}

export class LiveApiAuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "LiveApiAuthError";
  }
}

/** LIVE_API base URL (no trailing slash). */
export function liveApiBase(): string {
  return (envFlag("VITE_ATLAS_API_BASE") ?? "http://127.0.0.1:8765").replace(
    /\/$/,
    "",
  );
}

/** Per-launch READ Bearer token for Web reads (VITE_ only). */
export function liveApiToken(): string | undefined {
  const raw = envFlag("VITE_ATLAS_API_TOKEN");
  if (raw == null) {
    return undefined;
  }
  const trimmed = raw.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

/** True when DEMO_ONLY forces isolated stubs (no LIVE_API calls). */
export function liveApiDemoOnly(): boolean {
  const raw = (envFlag("VITE_ATLAS_DEMO_ONLY") ?? "").trim().toLowerCase();
  return raw === "1" || raw === "true" || raw === "yes";
}

/**
 * Build Authorization headers for LIVE_API.
 * Fail closed when the per-launch token is missing.
 */
export function liveApiAuthHeaders(): HeadersInit {
  const token = liveApiToken();
  if (!token) {
    throw new LiveApiAuthError(
      "VITE_ATLAS_API_TOKEN missing — LIVE_API requires SEC-009 Bearer auth. " +
        "Start via scripts/windows/atlas-start.ps1 (propagates per-launch ATLAS_API_READ_TOKEN) " +
        "or set VITE_ATLAS_API_TOKEN for this Vite process. Do not disable auth or hardcode tokens.",
    );
  }
  return { Authorization: `Bearer ${token}` };
}

/**
 * Fetch a LIVE_API path with Authorization: Bearer <read token>.
 * `path` must start with `/` (e.g. `/v1/meta`). Tokens never go in the URL.
 */
export async function liveApiFetch(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  if (!path.startsWith("/")) {
    throw new Error(`liveApiFetch path must start with '/': ${path}`);
  }
  const headers = new Headers(init?.headers);
  const auth = liveApiAuthHeaders() as Record<string, string>;
  for (const [key, value] of Object.entries(auth)) {
    headers.set(key, value);
  }
  return fetch(`${liveApiBase()}${path}`, { ...init, headers });
}
