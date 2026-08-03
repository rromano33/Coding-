import { NavLink } from "react-router-dom";

const TABS = [
  { to: "/", label: "Trades", icon: "📈", end: true },
  { to: "/performance", label: "Performance", icon: "📊", end: false },
  { to: "/diario", label: "Diário", icon: "📝", end: false },
  { to: "/risco", label: "Risco", icon: "🛡️", end: false },
];

export default function BottomNav() {
  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-slate-900/95 backdrop-blur border-t border-slate-800 pb-[env(safe-area-inset-bottom)]">
      <div className="max-w-lg mx-auto grid grid-cols-4">
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
