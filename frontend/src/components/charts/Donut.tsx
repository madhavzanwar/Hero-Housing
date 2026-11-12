import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from "recharts";
import { useTheme, chartColors } from "@/lib/theme";
import { TooltipBox } from "./ChartTooltip";

export interface DonutSlice {
  key: string;
  label: string;
  value: number;
  color: string;
}

/** Donut with a centre total and a side legend (FinPilot "Where your money went"). */
export function Donut({ data, centerLabel, centerValue }: { data: DonutSlice[]; centerLabel: string; centerValue: string }) {
  const [theme] = useTheme();
  const c = chartColors(theme);
  const total = data.reduce((a, d) => a + d.value, 0);
  const shown = data.filter((d) => d.value > 0);
  return (
    <div className="grid grid-cols-1 items-center gap-4 sm:grid-cols-[180px_1fr]">
      <div className="relative mx-auto size-[180px]">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={shown.length ? shown : [{ key: "none", label: "None", value: 1, color: c.track }]}
              dataKey="value"
              nameKey="label"
              innerRadius={58}
              outerRadius={84}
              paddingAngle={shown.length > 1 ? 3 : 0}
              cornerRadius={6}
              stroke={c.surface}
              strokeWidth={2}
              isAnimationActive={false}
            >
              {(shown.length ? shown : [{ key: "none", color: c.track }]).map((d) => (
                <Cell key={d.key} fill={d.color} />
              ))}
            </Pie>
            <Tooltip
              content={({ payload }) => {
                const p = payload?.[0]?.payload as DonutSlice | undefined;
                if (!p || p.key === "none") return null;
                return <TooltipBox rows={[{ label: p.label, value: `${p.value} (${total ? Math.round((p.value / total) * 100) : 0}%)`, color: p.color }]} />;
              }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-pewter">{centerLabel}</span>
          <span className="font-display text-2xl font-semibold text-ink tnum">{centerValue}</span>
        </div>
      </div>
      <ul className="min-w-0 space-y-2">
        {data.map((d) => (
          <li key={d.key} className="flex items-center gap-2 text-sm">
            <span className="size-2.5 shrink-0 rounded-full" style={{ background: d.color }} aria-hidden />
            <span className="min-w-0 flex-1 truncate text-graphite">{d.label}</span>
            <span className="font-semibold text-ink tnum">{d.value}</span>
            <span className="w-10 text-right text-xs text-pewter tnum">{total ? Math.round((d.value / total) * 100) : 0}%</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
