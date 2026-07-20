import { Outlet } from "react-router-dom";
import BottomNav from "./BottomNav";
import { useAuth } from "../auth/AuthContext";

export default function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen pb-20">
      <header className="sticky top-0 z-10 bg-slate-950/90 backdrop-blur border-b border-slate-800 px-4 py-3 flex items-center justify-between">
        <span className="font-semibold text-slate-100">Diário de Trades</span>
        <div className="flex items-center gap-3 text-sm text-slate-400">
          <span>{user?.display_name || user?.email}</span>
          <button onClick={logout} className="text-slate-500 hover:text-slate-300">
            Sair
          </button>
        </div>
      </header>
      <main className="max-w-lg mx-auto px-4 py-4">
        <Outlet />
      </main>
      <BottomNav />
    </div>
  );
}
