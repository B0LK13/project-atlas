import { useCallback, useEffect, useState } from "react";
import type { DensityMode, ScreenId, ThemeMode } from "./types";
import { AppShell } from "./components/AppShell";
import { CommandPalette } from "./components/CommandPalette";
import { useStudioData } from "./data/useStudioData";
import { MissionControlPage } from "./pages/MissionControlPage";
import { DesignLabPage } from "./pages/DesignLabPage";
import { ProjectionPage } from "./pages/ProjectionPage";
import {
  AgentsPage,
  ChroniclePage,
  KnowledgePage,
  ProjectsPage,
  RepositoryPage,
  SettingsPage,
  VerificationPage,
  WorkGraphPage,
} from "./pages/ProjectPages";

const paths: Record<ScreenId, string> = {
  "mission-control": "/mission-control",
  projects: "/projects",
  agents: "/agents",
  "work-graph": "/work-graph",
  repository: "/repository",
  verification: "/verification",
  knowledge: "/knowledge",
  chronicle: "/chronicle",
  settings: "/settings",
  "design-lab": "/design-lab",
};

function screenFromHash(): ScreenId {
  const path = window.location.hash.replace(/^#/, "") || "/mission-control";
  if (path.startsWith("/design-lab")) return "design-lab";
  return (Object.entries(paths).find(([, value]) => path === value)?.[0] as ScreenId | undefined) ?? "mission-control";
}

export default function App() {
  const studio = useStudioData();
  const [screen, setScreen] = useState<ScreenId>(screenFromHash);
  const [route, setRoute] = useState(window.location.hash);
  const closePalette = useCallback(() => setPalette(false), []);
  const [theme, setTheme] = useState<ThemeMode>("dark");
  const [density, setDensity] = useState<DensityMode>("compact");
  const [palette, setPalette] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  const navigate = useCallback((target: ScreenId) => {
    window.location.hash = paths[target];
    setScreen(target);
  }, []);

  useEffect(() => {
    const onHash = () => { setScreen(screenFromHash()); setRoute(window.location.hash); };
    window.addEventListener("hashchange", onHash);
    if (!window.location.hash) window.location.hash = paths["mission-control"];
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setPalette((value) => !value);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  let page = <MissionControlPage data={studio.data} onNavigate={navigate} />;
  if (screen === "projects") page = <ProjectsPage data={studio.data} />;
  if (screen === "agents") page = <AgentsPage data={studio.data} />;
  if (screen === "work-graph") page = <WorkGraphPage data={studio.data} />;
  if (screen === "repository") page = <RepositoryPage data={studio.data} />;
  if (screen === "verification") page = <VerificationPage data={studio.data} />;
  if (screen === "knowledge") page = <KnowledgePage data={studio.data} />;
  if (screen === "chronicle") page = <ChroniclePage data={studio.data} />;
  if (screen === "settings") {
    page = (
      <SettingsPage
        data={studio.data}
        theme={theme}
        density={density}
        preference={studio.preference}
        onTheme={setTheme}
        onDensity={setDensity}
        onPreference={studio.setPreference}
      />
    );
  }
  if (screen === "design-lab") page = <DesignLabPage key={route} data={studio.data} />;
  if (studio.data.source.kind !== "DESIGN_PREVIEW" && screen !== "settings" && screen !== "design-lab") {
    page = <ProjectionPage data={studio.data} screen={screen} />;
  }

  return (
    <div data-theme={theme} data-density={density}>
      <AppShell
        active={screen}
        onNavigate={navigate}
        data={studio.data}
        loading={studio.loading}
        error={studio.error}
        theme={theme}
        density={density}
        onTheme={() => setTheme((value) => (value === "dark" ? "light" : "dark"))}
        onDensity={() => setDensity((value) => (value === "comfortable" ? "compact" : value === "compact" ? "focus" : "comfortable"))}
        onRefresh={() => void studio.refresh()}
        onPalette={() => setPalette(true)}
        mobileOpen={mobileOpen}
        onMobileOpen={setMobileOpen}
      >
        {page}
      </AppShell>
      <CommandPalette open={palette} onClose={closePalette} onNavigate={navigate} />
    </div>
  );
}
