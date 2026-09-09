import { useCallback, useEffect, useRef, useState } from "react";
import { fixtureEnvelope } from "./fixture";
import { envelopeFromProjection, unavailableEnvelope, loadProjection } from "./adapter";
import type { StudioEnvelope } from "../types";

export type SourcePreference = "projection" | "fixture";

const REQUEST_TIMEOUT_MS = 25_000;
const LOCAL_FRESHNESS_INTERVAL_MS = 1_000;

export function useStudioData() {
  const [data, setData] = useState<StudioEnvelope>(() => unavailableEnvelope("Loading A1 projection"));
  const [preference, setPreferenceState] = useState<SourcePreference>("projection");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const preferenceRef = useRef<SourcePreference>("projection");
  const request = useRef(0);
  const activeController = useRef<AbortController | null>(null);

  const cancelActiveRequest = useCallback(() => {
    request.current += 1;
    activeController.current?.abort();
    activeController.current = null;
  }, []);

  const refresh = useCallback(async () => {
    const token = ++request.current;
    activeController.current?.abort();
    activeController.current = null;

    if (preferenceRef.current === "fixture") {
      setData(fixtureEnvelope);
      setError(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    setData(unavailableEnvelope("Loading A1 projection"));
    const controller = new AbortController();
    activeController.current = controller;
    let timedOut = false;
    const timeout = window.setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, REQUEST_TIMEOUT_MS);
    try {
      const next = await loadProjection(controller.signal);
      if (request.current === token && preferenceRef.current === "projection") {
        setData(next);
        setError(null);
      }
    } catch (caught) {
      if (request.current === token && preferenceRef.current === "projection") {
        const message = timedOut
          ? "Projection request timed out after 25 seconds"
          : caught instanceof Error
            ? caught.message
            : "unknown bridge failure";
        setData(unavailableEnvelope(message));
        setError(message);
      }
    } finally {
      window.clearTimeout(timeout);
      if (activeController.current === controller) activeController.current = null;
      if (request.current === token) setLoading(false);
    }
  }, []);

  const setPreference = useCallback((next: SourcePreference) => {
    if (preferenceRef.current === next) return;
    preferenceRef.current = next;
    cancelActiveRequest();
    setPreferenceState(next);
    setError(null);
    if (next === "fixture") {
      setData(fixtureEnvelope);
      setLoading(false);
    } else {
      setData(unavailableEnvelope("Loading A1 projection"));
      setLoading(true);
    }
  }, [cancelActiveRequest]);

  useEffect(() => {
    void refresh();
  }, [preference, refresh]);

  useEffect(() => () => cancelActiveRequest(), [cancelActiveRequest]);

  useEffect(() => {
    if (data.source.kind !== "PROJECTION" || data.projection.freshness.state !== "LIVE") return;
    const fingerprint = data.projection.snapshot_fingerprint;
    const interval = window.setInterval(() => {
      setData((current) => {
        if (current.source.kind !== "PROJECTION"
            || current.projection.snapshot_fingerprint !== fingerprint) return current;
        return envelopeFromProjection(current.projection);
      });
    }, LOCAL_FRESHNESS_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [data.projection.freshness.state, data.projection.snapshot_fingerprint, data.source.kind]);

  return {
    data,
    error,
    loading,
    preference,
    setPreference,
    refresh,
  };
}
