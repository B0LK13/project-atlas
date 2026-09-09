import { useCallback, useEffect, useRef, useState } from "react";
import { fixtureEnvelope } from "./fixture";
import { unavailableEnvelope, loadProjection } from "./adapter";
import type { StudioEnvelope } from "../types";

export type SourcePreference = "projection" | "fixture";

export function useStudioData() {
  const [data, setData] = useState<StudioEnvelope>(() => unavailableEnvelope("Loading A1 projection"));
  const [preference, setPreference] = useState<SourcePreference>("projection");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const request = useRef(0);

  const refresh = useCallback(async () => {
    const token = ++request.current;
    if (preference === "fixture") {
      setData(fixtureEnvelope);
      setError(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setData(unavailableEnvelope("Loading A1 projection"));
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 4_000);
    try {
      const next = await loadProjection(controller.signal);
      if (request.current === token) {
        setData(next);
        setError(null);
      }
    } catch (caught) {
      if (request.current === token) {
        const message = caught instanceof Error ? caught.message : "unknown bridge failure";
        setData(unavailableEnvelope(message));
        setError(message);
      }
    } finally {
      window.clearTimeout(timeout);
      if (request.current === token) setLoading(false);
    }
  }, [preference]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return {
    data,
    error,
    loading,
    preference,
    setPreference,
    refresh,
  };
}
