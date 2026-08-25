import { Navigate, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import LedgerDeskPage from "./pages/design-lab/LedgerDeskPage";
import SignalRackPage from "./pages/design-lab/SignalRackPage";
import CartographQuietPage from "./pages/design-lab/CartographQuietPage";
import TerminalHonestPage from "./pages/design-lab/TerminalHonestPage";
import ProjectsPage from "./pages/production/ProjectsPage";
import DiscoveryPage from "./pages/production/DiscoveryPage";
import KnowledgePage from "./pages/production/KnowledgePage";
import GraphPage from "./pages/production/GraphPage";
import OpsHealthPage from "./pages/production/OpsHealthPage";
import CommandCenterPage from "./pages/production/CommandCenterPage";
import MissionControlPage from "./pages/production/MissionControlPage";
import WorkspacePage from "./pages/production/WorkspacePage";
import TimeMachinePage from "./pages/production/TimeMachinePage";
import ContextPage from "./pages/production/ContextPage";
import AskPage from "./pages/production/AskPage";
import RoadmapPage from "./pages/production/RoadmapPage";
import IntelligencePage from "./pages/production/IntelligencePage";
import UnknownPage from "./pages/production/UnknownPage";
import ChangedPage from "./pages/production/ChangedPage";
import InboxPage from "./pages/production/InboxPage";
import OverviewPage from "./pages/production/OverviewPage";
import DecisionsPage from "./pages/production/DecisionsPage";
import AttentionPage from "./pages/production/AttentionPage";

/** Client router — production shell + design-lab. UI ≠ canonical. */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/projects" element={<ProjectsPage />} />
      <Route path="/discovery" element={<DiscoveryPage />} />
      <Route path="/knowledge" element={<KnowledgePage />} />
      <Route path="/graph" element={<GraphPage />} />
      <Route path="/ops" element={<OpsHealthPage />} />
      <Route path="/command-center" element={<CommandCenterPage />} />
      <Route path="/mission-control" element={<MissionControlPage />} />
      <Route path="/workspace" element={<WorkspacePage />} />
      <Route path="/time-machine" element={<TimeMachinePage />} />
      <Route path="/context" element={<ContextPage />} />
      <Route path="/ask" element={<AskPage />} />
      <Route path="/roadmap" element={<RoadmapPage />} />
      <Route path="/intelligence" element={<IntelligencePage />} />
      <Route path="/unknown" element={<UnknownPage />} />
      <Route path="/changed" element={<ChangedPage />} />
      <Route path="/inbox" element={<InboxPage />} />
      <Route path="/overview" element={<OverviewPage />} />
      <Route path="/decisions" element={<DecisionsPage />} />
      <Route path="/attention" element={<AttentionPage />} />
      <Route path="/design-lab/ledger-desk" element={<LedgerDeskPage />} />
      <Route path="/design-lab/signal-rack" element={<SignalRackPage />} />
      <Route path="/design-lab/cartograph-quiet" element={<CartographQuietPage />} />
      <Route path="/design-lab/terminal-honest" element={<TerminalHonestPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
