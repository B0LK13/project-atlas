// @vitest-environment jsdom

import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import generatedPacket from "./test-fixtures/generated-a1-packet.json";
import { fixtureEnvelope } from "./fixture";
import { useStudioData } from "./useStudioData";
import type { MissionControlProjection } from "../types";

function packet(): MissionControlProjection {
  return structuredClone(generatedPacket) as MissionControlProjection;
}

function jsonResponse(value: MissionControlProjection): Response {
  return new Response(JSON.stringify(value), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

async function flush() {
  await act(async () => {
    await Promise.resolve();
  });
}

describe("useStudioData", () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("recomputes local age until a LIVE packet becomes locally stale", async () => {
    vi.useFakeTimers();
    vi.setSystemTime("2026-09-09T12:00:00Z");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(packet())));
    const { result } = renderHook(() => useStudioData());
    await flush();

    expect(result.current.data.source.current).toBe(true);
    expect(result.current.data.source.localFreshness?.ageSeconds).toBe(0);

    act(() => vi.advanceTimersByTime(121_000));

    expect(result.current.data.source.current).toBe(false);
    expect(result.current.data.source.localFreshness?.state).toBe("STALE");
    expect(result.current.data.projection.generated_at_utc).toBe("2026-09-09T12:00:00Z");
    expect(result.current.data.projection.freshness.age_seconds).toBe(0);
  });

  it("clears operational state when a refresh fails", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(packet()))
      .mockRejectedValueOnce(new Error("bridge unavailable"));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useStudioData());
    await waitFor(() => expect(result.current.data.source.kind).toBe("PROJECTION"));

    await act(async () => {
      await result.current.refresh();
    });

    expect(result.current.data.source.kind).toBe("UNAVAILABLE");
    expect(result.current.data.projection.snapshot_fingerprint).toBe("");
    expect(result.current.error).toContain("bridge unavailable");
  });

  it("aborts a pending projection request when fixture mode is selected", async () => {
    const pending = deferred<Response>();
    let requestSignal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn((_url: unknown, init?: RequestInit) => {
      requestSignal = init?.signal ?? undefined;
      return pending.promise;
    }));
    const { result } = renderHook(() => useStudioData());
    await flush();

    act(() => result.current.setPreference("fixture"));

    expect(requestSignal?.aborted).toBe(true);
    await waitFor(() => expect(result.current.data).toBe(fixtureEnvelope));
    pending.resolve(jsonResponse(packet()));
    await flush();
    expect(result.current.data).toBe(fixtureEnvelope);
  });

  it("isolates fixture refreshes from the bridge", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(packet()));
    vi.stubGlobal("fetch", fetchMock);
    const { result } = renderHook(() => useStudioData());
    await waitFor(() => expect(result.current.data.source.kind).toBe("PROJECTION"));

    act(() => result.current.setPreference("fixture"));
    await waitFor(() => expect(result.current.data).toBe(fixtureEnvelope));
    const callsBeforeRefresh = fetchMock.mock.calls.length;
    await act(async () => {
      await result.current.refresh();
    });

    expect(fetchMock).toHaveBeenCalledTimes(callsBeforeRefresh);
    expect(result.current.data).toBe(fixtureEnvelope);
  });

  it("aborts the active request on unmount and ignores its late result", async () => {
    const pending = deferred<Response>();
    let requestSignal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn((_url: unknown, init?: RequestInit) => {
      requestSignal = init?.signal ?? undefined;
      return pending.promise;
    }));
    const { unmount } = renderHook(() => useStudioData());
    await flush();

    unmount();

    expect(requestSignal?.aborted).toBe(true);
    pending.resolve(jsonResponse(packet()));
    await flush();
  });

  it("caps a projection request at 25 seconds", async () => {
    vi.useFakeTimers();
    vi.setSystemTime("2026-09-09T12:00:00Z");
    let requestSignal: AbortSignal | undefined;
    vi.stubGlobal("fetch", vi.fn((_url: unknown, init?: RequestInit) => {
      requestSignal = init?.signal ?? undefined;
      return new Promise<Response>((_resolve, reject) => {
        requestSignal?.addEventListener("abort", () => reject(new DOMException("Aborted", "AbortError")));
      });
    }));
    const { result } = renderHook(() => useStudioData());
    await flush();

    act(() => vi.advanceTimersByTime(24_999));
    expect(requestSignal?.aborted).toBe(false);
    await act(async () => vi.advanceTimersByTime(1));

    expect(requestSignal?.aborted).toBe(true);
    expect(result.current.data.source.kind).toBe("UNAVAILABLE");
  });
});
