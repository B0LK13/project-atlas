import { useCallback, useEffect, useRef, useState } from "react";
import { loadMissionJourney, loadTaskContext } from "./missionContracts";
import type { MissionJourneyProjection, TaskContextProjection } from "../types";

export function useMissionContracts(enabled: boolean) {
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
    try { setTaskContext(await loadTaskContext(lane, controller.signal)); }
    catch (error) { if (!controller.signal.aborted) setTaskError(error instanceof Error ? error.message : "Task Context unavailable"); }
    finally { if (taskRequest.current === controller) { taskRequest.current = null; setTaskLoading(false); } }
  }, []);

  useEffect(() => {
    if (!enabled) { journeyRequest.current?.abort(); return; }
    void refreshJourney();
    return () => journeyRequest.current?.abort();
  }, [enabled, refreshJourney]);

  useEffect(() => () => { taskRequest.current?.abort(); }, []);
  return { journey, journeyError, journeyLoading, refreshJourney, taskContext, taskError, taskLoading, loadTask };
}
