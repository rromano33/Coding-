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
import MarketNotesPage from "./pages/MarketNotesPage";
import JournalPage from "./pages/JournalPage";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={<TradesPage />} />
              <Route path="/trades/new" element={<TradeFormPage />} />
              <Route path="/trades/:id" element={<TradeDetailPage />} />
              <Route path="/trades/:id/edit" element={<TradeFormPage />} />
              <Route path="/performance" element={<PerformancePage />} />
              <Route path="/mercado" element={<MarketNotesPage />} />
              <Route path="/diario" element={<JournalPage />} />
            </Route>
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
