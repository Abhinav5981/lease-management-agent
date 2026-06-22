import type { LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: number | string;
  sub?: string;
  icon: LucideIcon;
  iconColor?: string;
}

export function StatCard({ label, value, sub, icon: Icon, iconColor = "text-blue-600" }: StatCardProps) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5 flex items-start gap-4">
      <div className={`mt-0.5 p-2.5 rounded-lg bg-slate-50 ${iconColor}`}>
        <Icon size={20} />
      </div>
      <div>
        <p className="text-sm text-slate-500 font-medium">{label}</p>
        <p className="text-2xl font-bold text-slate-900 mt-0.5">{value}</p>
        {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
      </div>
    </div>
  );
}
