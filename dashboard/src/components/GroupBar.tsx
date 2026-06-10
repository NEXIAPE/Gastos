import type { Slice } from "../lib/aggregate";
import { GROUP_COLOR, type ExpenseGroup } from "../lib/types";
import { soles } from "../lib/format";

// Barra apilada de "Tipo de Gasto" + leyenda con montos y porcentajes.
export default function GroupBar({ data }: { data: Slice[] }) {
  const total = data.reduce((a, s) => a + s.value, 0);
  if (total <= 0) return <p className="muted">Sin datos.</p>;

  return (
    <div>
      <div className="groupbar">
        {data.map((s) => (
          <div
            key={s.key}
            className="groupbar-seg"
            style={{
              width: `${(s.value / total) * 100}%`,
              background: GROUP_COLOR[s.key as ExpenseGroup] ?? "#9ca3af",
            }}
            title={`${s.key}: ${soles(s.value)}`}
          />
        ))}
      </div>
      <div className="grouplegend">
        {data.map((s) => (
          <div key={s.key} className="grouplegend-item">
            <span className="dot" style={{ background: GROUP_COLOR[s.key as ExpenseGroup] ?? "#9ca3af" }} />
            <span className="grouplegend-name">{s.key}</span>
            <span className="grouplegend-val">
              {soles(s.value)} <span className="muted">· {Math.round((s.value / total) * 100)}%</span>
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
