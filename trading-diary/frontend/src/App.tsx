import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import LoginPage from "./auth/LoginPage";
import RegisterPage from "./auth/RegisterPage";
import ProtectedRoute from "./components/ProtectedRoute";
import Layout from "./components/Layout";
import TradesPage from "./pages/TradesPage";
import TradeFormPage from "./pages/TradeFormPage";
import TradeDetailPage from "./pages/TradeDetailPage";
import PerformancePage from "./pages/PerformancePage";
import DailyNotePage from "./pages/DailyNotePage";
import RiskStatusPage from "./pages/RiskStatusPage";
import RiskSettingsPage from "./pages/RiskSettingsPage";
import JournalPage from "./pages/JournalPage";

// Trades/Performance/Risco/Diário macro (o antigo "diário de trades" completo)
// saíram da navegação — o app virou um diário simples de texto + mood
// (ver JournalPage). As rotas continuam montadas (código e dados de schema
// intactos) só por reversibilidade; não tem mais link nenhum pra elas.
export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<JournalPage />} />
              <Route path="/trades" element={<TradesPage />} />
              <Route path="/trades/new" element={<TradeFormPage />} />
              <Route path="/trades/:id" element={<TradeDetailPage />} />
              <Route path="/trades/:id/edit" element={<TradeFormPage />} />
              <Route path="/performance" element={<PerformancePage />} />
              <Route path="/diario-macro" element={<DailyNotePage />} />
              <Route path="/risco" element={<RiskStatusPage />} />
              <Route path="/risco/opcoes" element={<RiskSettingsPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
