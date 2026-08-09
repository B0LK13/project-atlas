import { Navigate, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import LedgerDeskPage from "./pages/design-lab/LedgerDeskPage";
import SignalRackPage from "./pages/design-lab/SignalRackPage";
import CartographQuietPage from "./pages/design-lab/CartographQuietPage";
import TerminalHonestPage from "./pages/design-lab/TerminalHonestPage";
import ProjectsPage from "./pages/production/ProjectsPage";
import KnowledgePage from "./pages/production/KnowledgePage";
import GraphPage from "./pages/production/GraphPage";
import OpsHealthPage from "./pages/production/OpsHealthPage";
import CommandCenterPage from "./pages/production/CommandCenterPage";
import MissionControlPage from "./pages/production/MissionControlPage";
import WorkspacePage from "./pages/production/WorkspacePage";

/** Client router — production shell + design-lab. UI ≠ canonical. */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/projects" element={<ProjectsPage />} />
      <Route path="/knowledge" element={<KnowledgePage />} />
      <Route path="/graph" element={<GraphPage />} />
      <Route path="/ops" element={<OpsHealthPage />} />
      <Route path="/command-center" element={<CommandCenterPage />} />
      <Route path="/mission-control" element={<MissionControlPage />} />
      <Route path="/workspace" element={<WorkspacePage />} />
      <Route path="/design-lab/ledger-desk" element={<LedgerDeskPage />} />
      <Route path="/design-lab/signal-rack" element={<SignalRackPage />} />
      <Route path="/design-lab/cartograph-quiet" element={<CartographQuietPage />} />
      <Route path="/design-lab/terminal-honest" element={<TerminalHonestPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
