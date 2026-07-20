interface StatCardProps {
  label: string;
  value: string;
  accent?: "green" | "red" | "neutral";
}

export default function StatCard({ label, value, accent = "neutral" }: StatCardProps) {
  const color = accent === "green" ? "text-green-400" : accent === "red" ? "text-red-400" : "text-slate-100";
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl px-3 py-3">
      <p className="text-xs text-slate-500 mb-1">{label}</p>
      <p className={`text-lg font-semibold ${color}`}>{value}</p>
    </div>
  );
}
