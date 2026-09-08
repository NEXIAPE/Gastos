import {
  Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import type { Slice } from "../lib/aggregate";
import { soles } from "../lib/format";
import { groupOf } from "../lib/categories";
import { groupColor, useDarkMode } from "../lib/theme";
import type { ExpenseGroup } from "../lib/types";

// Cada categoría hereda el color de su Tipo de Gasto (7 tonos fijos y
// validados) en vez de un color aleatorio por comercio/categoría — con 30+
// categorías, 30+ tonos distintos serían ilegibles y no pasarían el chequeo
// de separación CVD. La etiqueta de texto (siempre visible) distingue cada
// categoría dentro de su familia de color.
function sliceColor(categoryName: string, dark: boolean): string {
  return groupColor(groupOf(categoryName), dark);
}

/** Leyenda de los Tipo de Gasto presentes (nunca más de 7 — no una por categoría). */
function GroupLegend({ groups, dark }: { groups: ExpenseGroup[]; dark: boolean }) {
  return (
    <div className="grouplegend" style={{ marginTop: 4 }}>
      {groups.map((g) => (
        <div key={g} className="grouplegend-item">
          <span className="dot" style={{ background: groupColor(g, dark) }} />
          <span className="grouplegend-name">{g}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * Gasto por categoría, en barras horizontales (no dona): con 30+ categorías
 * posibles, una dona con tantos gajos deja de leerse — pasado ~7 segmentos
 * las clases se confunden. Una barra ordenada por monto escala a cualquier
 * cantidad de categorías sin ese límite. Cada barra se colorea por su Tipo
 * de Gasto para agrupar visualmente sin inventar un tono por categoría.
 */
export function CategoryBars({ data }: { data: Slice[] }) {
  const dark = useDarkMode();
  if (data.length === 0) return <p className="muted">Sin datos.</p>;
  const groups = [...new Set(data.map((d) => groupOf(d.key)))];
  return (
    <div>
      <ResponsiveContainer width="100%" height={Math.max(220, data.length * 30)}>
        <BarChart data={data} layout="vertical" margin={{ left: 10, right: 16 }}>
          <XAxis type="number" tickFormatter={(v) => `S/${v}`} tick={{ fill: "#94a3b8", fontSize: 12 }} />
          <YAxis type="category" dataKey="key" width={130} tick={{ fill: "#94a3b8", fontSize: 11 }} />
          <Tooltip formatter={(v: number) => soles(v)} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.map((d) => <Cell key={d.key} fill={sliceColor(d.key, dark)} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <GroupLegend groups={groups} dark={dark} />
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
