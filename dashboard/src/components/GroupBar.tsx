import type { Slice } from "../lib/aggregate";
import type { ExpenseGroup } from "../lib/types";
import { soles } from "../lib/format";
import { groupColor, useDarkMode } from "../lib/theme";

// Barra apilada de "Tipo de Gasto" + leyenda con montos y porcentajes.
export default function GroupBar({ data }: { data: Slice[] }) {
  const dark = useDarkMode();
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
              background: groupColor(s.key as ExpenseGroup, dark),
            }}
            title={`${s.key}: ${soles(s.value)}`}
          />
        ))}
      </div>
      <div className="grouplegend">
        {data.map((s) => (
          <div key={s.key} className="grouplegend-item">
            <span className="dot" style={{ background: groupColor(s.key as ExpenseGroup, dark) }} />
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
