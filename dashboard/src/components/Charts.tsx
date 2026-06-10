import {
  Bar, BarChart, Cell, Legend, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import type { Slice } from "../lib/aggregate";
import { colorFor, soles } from "../lib/format";

export function Donut({ data }: { data: Slice[] }) {
  if (data.length === 0) return <p className="muted">Sin datos.</p>;
  return (
    <ResponsiveContainer width="100%" height={300}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="key" innerRadius={70} outerRadius={110} paddingAngle={1}>
          {data.map((d) => <Cell key={d.key} fill={colorFor(d.key)} />)}
        </Pie>
        <Tooltip formatter={(v: number) => soles(v)} />
        <Legend />
      </PieChart>
    </ResponsiveContainer>
  );
}

export function Bars({ data, color = "#2563eb", horizontal = false }:
  { data: Slice[]; color?: string; horizontal?: boolean }) {
  if (data.length === 0) return <p className="muted">Sin datos.</p>;
  if (horizontal) {
    return (
      <ResponsiveContainer width="100%" height={Math.max(220, data.length * 34)}>
        <BarChart data={data} layout="vertical" margin={{ left: 20, right: 20 }}>
          <XAxis type="number" tickFormatter={(v) => `S/${v}`} />
          <YAxis type="category" dataKey="key" width={140} />
          <Tooltip formatter={(v: number) => soles(v)} />
          <Bar dataKey="value" fill={color} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  }
  return (
    <ResponsiveContainer width="100%" height={300}>
      <BarChart data={data} margin={{ left: 10, right: 10 }}>
        <XAxis dataKey="key" />
        <YAxis tickFormatter={(v) => `S/${v}`} />
        <Tooltip formatter={(v: number) => soles(v)} />
        <Bar dataKey="value" fill={color} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
