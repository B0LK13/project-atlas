import type { ValidateFunction } from "ajv";
import { validateMissionJourney, validateTaskContext } from "virtual:atlas-projection-validators";
import type { MissionJourneyProjection, TaskContextProjection } from "../types";
import { ProjectionContractError } from "./adapter";

const origin = new URL(import.meta.env.VITE_ATLAS_STUDIO_BRIDGE_URL ?? "http://127.0.0.1:47631/v1/mission-control").origin;

function assertContract<T>(label: string, validator: ValidateFunction, value: unknown): asserts value is T {
  if (!validator(value)) throw new ProjectionContractError(`${label} contract failed`);
  const record = value as { honesty?: unknown };
  if (!record.honesty || typeof record.honesty !== "object" || Object.values(record.honesty).some((flag) => flag !== true)) {
    throw new ProjectionContractError(`${label} honesty contract failed closed`);
  }
}

async function load<T>(path: string, validator: ValidateFunction, label: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${origin}${path}`, { headers: { Accept: "application/json" }, cache: "no-store", signal });
  if (!response.ok) {
    let reason = `Bridge returned ${response.status}`;
    try { const body = await response.json(); if (typeof body.reason === "string") reason = body.reason; } catch { /* status is sufficient */ }
    throw new ProjectionContractError(reason);
  }
  const packet: unknown = await response.json();
  assertContract<T>(label, validator, packet);
  return packet;
}

export const loadMissionJourney = (signal?: AbortSignal) =>
  load<MissionJourneyProjection>("/v1/mission-journey", validateMissionJourney, "Mission Journey", signal);

export const loadTaskContext = (lane: string, signal?: AbortSignal) =>
  load<TaskContextProjection>(`/v1/task-context?lane=${encodeURIComponent(lane)}`, validateTaskContext, "Task Context", signal);
