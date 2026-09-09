import { NavLink } from "react-router-dom";

// App simplificado pra só um diário de texto + mood — as outras abas
// (Trades/Performance/Risco) saíram da navegação, ver App.tsx.
const TABS = [{ to: "/", label: "Diário", icon: "📝", end: true }];

export default function BottomNav() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-slate-900/95 backdrop-blur border-t border-slate-800 pb-[env(safe-area-inset-bottom)]">
      <div className="max-w-lg mx-auto grid grid-cols-1">
        {TABS.map((tab) => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) =>
              `flex flex-col items-center justify-center gap-0.5 py-2.5 text-xs ${
                isActive ? "text-green-400" : "text-slate-400"
              }`
            }
          >
            <span className="text-lg leading-none">{tab.icon}</span>
            {tab.label}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}
