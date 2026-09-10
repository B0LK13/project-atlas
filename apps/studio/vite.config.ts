import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import Ajv2020 from "ajv/dist/2020.js";
import standaloneCode from "ajv/dist/standalone/index.js";

// D-006: compile canonical contracts at build time; native CSP forbids eval.
const validatorSchemas = {
  validateMissionControl: "atlas_studio_mission_control_v1",
  validateMissionJourney: "atlas_studio_mission_journey_v1",
  validateTaskContext: "atlas_studio_task_context_v1",
  validateStudioSnapshot: "atlas_studio_snapshot_v1",
  validateStudioEvent: "atlas_studio_event_v1",
  validateControlView: "atlas_global_control_view_v1",
  validateTelemetry: "atlas_coordination_telemetry_v1",
  validateEfficiencyMetrics: "atlas_efficiency_metrics_v1",
};

function projectionValidators(): Plugin {
  const id = "virtual:atlas-projection-validators";
  return {
    name: "atlas-projection-validators",
    resolveId(source: string) { return source === id ? `\0${id}` : undefined; },
    load(source: string) {
      if (source !== `\0${id}`) return;
      const ajv = new Ajv2020({ allErrors: true, strict: false, code: { source: true, esm: true } });
      const exports: Record<string, string> = {};
      for (const [name, filename] of Object.entries(validatorSchemas)) {
        const path = fileURLToPath(new URL(`../../schemas/${filename}.schema.json`, import.meta.url));
        this.addWatchFile(path);
        const schema = JSON.parse(readFileSync(path, "utf8"));
        ajv.addSchema(schema, filename);
        exports[name] = filename;
      }
      // Ajv's standalone Unicode-length helper is emitted as CommonJS even in ESM mode.
      // Import the same helper statically so no require/eval reaches the WebView.
      const code = standaloneCode(ajv, exports).replaceAll(
        'require("ajv/dist/runtime/ucs2length").default', "ucs2length",
      );
      if (code.includes("require(")) throw new Error("Unsupported standalone validator runtime dependency");
      return 'import ucs2length from "ajv/dist/runtime/ucs2length.js";\n' + code;
    },
  };
}

export default defineConfig({
  plugins: [projectionValidators(), react()],
  clearScreen: false,
  server: {
    host: "127.0.0.1",
    port: 1420,
    strictPort: true,
  },
  preview: {
    host: "127.0.0.1",
    port: 4420,
    strictPort: true,
  },
});
