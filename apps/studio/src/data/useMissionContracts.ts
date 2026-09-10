import { useCallback, useEffect, useRef, useState } from "react";
import { loadMissionJourney, loadTaskContext } from "./missionContracts";
import type { MissionJourneyProjection, TaskContextProjection } from "../types";

const presentationStateVersion = 1;

export function useMissionContracts(enabled: boolean, repository?: string) {
  const [journey, setJourney] = useState<MissionJourneyProjection | null>(null);
  const [journeyError, setJourneyError] = useState<string | null>(null);
  const [journeyLoading, setJourneyLoading] = useState(false);
  const [taskContext, setTaskContext] = useState<TaskContextProjection | null>(null);
  const [taskError, setTaskError] = useState<string | null>(null);
  const [taskLoading, setTaskLoading] = useState(false);
  const journeyRequest = useRef<AbortController | null>(null);
  const taskRequest = useRef<AbortController | null>(null);

  const refreshJourney = useCallback(async () => {
    journeyRequest.current?.abort();
    const controller = new AbortController(); journeyRequest.current = controller;
    setJourneyLoading(true); setJourneyError(null);
    try { setJourney(await loadMissionJourney(controller.signal)); }
    catch (error) { if (!controller.signal.aborted) { setJourney(null); setJourneyError(error instanceof Error ? error.message : "Mission Journey unavailable"); } }
    finally { if (journeyRequest.current === controller) { journeyRequest.current = null; setJourneyLoading(false); } }
  }, []);

  const loadTask = useCallback(async (lane: string) => {
    taskRequest.current?.abort();
    const controller = new AbortController(); taskRequest.current = controller;
    setTaskLoading(true); setTaskError(null); setTaskContext(null);
    try {
      const packet = await loadTaskContext(lane, controller.signal);
      setTaskContext(packet);
      try { window.localStorage.setItem("atlas.selectedLane", JSON.stringify({ version: presentationStateVersion, sourceMode: "PROJECTION", lane: packet.lane, repository: packet.repository ?? repository ?? null })); } catch { /* optional presentation state */ }
    }
    catch (error) { if (!controller.signal.aborted) setTaskError(error instanceof Error ? error.message : "Task Context unavailable"); }
    finally { if (taskRequest.current === controller) { taskRequest.current = null; setTaskLoading(false); } }
  }, []);

  useEffect(() => {
    if (!enabled || typeof window === "undefined") return;
    let storedLane: string | null = null;
    try {
      const raw = window.localStorage.getItem("atlas.selectedLane");
      const parsed: unknown = raw ? JSON.parse(raw) : null;
      if (parsed && typeof parsed === "object" && "version" in parsed && parsed.version === presentationStateVersion && "sourceMode" in parsed && parsed.sourceMode === "PROJECTION" && "lane" in parsed && typeof parsed.lane === "string"
        && (!("repository" in parsed) || parsed.repository == null || !repository || parsed.repository === repository)) storedLane = parsed.lane;
      else if (raw) window.localStorage.removeItem("atlas.selectedLane");
    } catch { /* optional presentation state */ }
    if (storedLane) void loadTask(storedLane);
  }, [enabled, loadTask, repository]);

  useEffect(() => {
    if (!enabled) { journeyRequest.current?.abort(); return; }
    void refreshJourney();
    return () => journeyRequest.current?.abort();
  }, [enabled, refreshJourney]);

  useEffect(() => () => { taskRequest.current?.abort(); }, []);
  return { journey, journeyError, journeyLoading, refreshJourney, taskContext, taskError, taskLoading, loadTask };
}
