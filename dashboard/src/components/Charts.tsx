import {
  Bar, BarChart, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Slice } from "../lib/aggregate";
import { colorFor, soles } from "../lib/format";

function Legend({ data, total }: { data: Slice[]; total: number }) {
  return (
    <div className="grouplegend" style={{ marginTop: 12 }}>
      {data.map((d) => (
        <div key={d.key} className="grouplegend-item">
          <span className="dot" style={{ background: colorFor(d.key) }} />
          <span className="grouplegend-name">{d.key}</span>
          <span className="grouplegend-val">
            {soles(d.value)} <span className="muted">· {total ? Math.round((d.value / total) * 100) : 0}%</span>
          </span>
        </div>
      ))}
    </div>
  );
}

export function Donut({ data }: { data: Slice[] }) {
  if (data.length === 0) return <p className="muted">Sin datos.</p>;
  const total = data.reduce((a, s) => a + s.value, 0);
  return (
    <div>
      <ResponsiveContainer width="100%" height={230}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="key" innerRadius={58} outerRadius={98} paddingAngle={1}>
            {data.map((d) => <Cell key={d.key} fill={colorFor(d.key)} />)}
          </Pie>
          <Tooltip formatter={(v: number) => soles(v)} />
        </PieChart>
      </ResponsiveContainer>
      <Legend data={data} total={total} />
    </div>
  );
}

export function Bars({ data, color = "#6c5ce7", horizontal = false }:
  { data: Slice[]; color?: string; horizontal?: boolean }) {
  if (data.length === 0) return <p className="muted">Sin datos.</p>;
  if (horizontal) {
    return (
      <ResponsiveContainer width="100%" height={Math.max(220, data.length * 34)}>
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 16 }}>
          <XAxis type="number" tickFormatter={(v) => `S/${v}`} tick={{ fill: "#94a3b8", fontSize: 12 }} />
          <YAxis type="category" dataKey="key" width={120} tick={{ fill: "#94a3b8", fontSize: 11 }} />
          <Tooltip formatter={(v: number) => soles(v)} />
          <Bar dataKey="value" fill={color} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={280}>
      <BarChart data={data} margin={{ left: 6, right: 6 }}>
        <XAxis dataKey="key" tick={{ fill: "#94a3b8", fontSize: 11 }} />
        <YAxis tickFormatter={(v) => `S/${v}`} tick={{ fill: "#94a3b8", fontSize: 12 }} />
        <Tooltip formatter={(v: number) => soles(v)} />
        <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
