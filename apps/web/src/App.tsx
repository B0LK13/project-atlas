import { Navigate, Route, Routes } from "react-router-dom";
import HomePage from "./pages/HomePage";
import LedgerDeskPage from "./pages/design-lab/LedgerDeskPage";
import SignalRackPage from "./pages/design-lab/SignalRackPage";
import CartographQuietPage from "./pages/design-lab/CartographQuietPage";
import TerminalHonestPage from "./pages/design-lab/TerminalHonestPage";

/** Client router — design-lab prototypes + foundation hub. UI ≠ canonical. */
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/design-lab/ledger-desk" element={<LedgerDeskPage />} />
      <Route path="/design-lab/signal-rack" element={<SignalRackPage />} />
      <Route path="/design-lab/cartograph-quiet" element={<CartographQuietPage />} />
      <Route path="/design-lab/terminal-honest" element={<TerminalHonestPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
