/// <reference types="vite/client" />

// Build-time canonical validators retain Ajv error semantics without runtime eval.
declare module "virtual:atlas-projection-validators" {
  import type { ValidateFunction } from "ajv";
  export const validateMissionControl: ValidateFunction;
  export const validateMissionJourney: ValidateFunction;
  export const validateTaskContext: ValidateFunction;
  export const validateStudioSnapshot: ValidateFunction;
  export const validateStudioEvent: ValidateFunction;
  export const validateControlView: ValidateFunction;
  export const validateTelemetry: ValidateFunction;
  export const validateEfficiencyMetrics: ValidateFunction;
}
