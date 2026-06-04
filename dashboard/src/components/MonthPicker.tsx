import { lastNMonths } from "../lib/time";

export default function MonthPicker({
  value, onChange,
}: { value: string; onChange: (key: string) => void }) {
  const months = lastNMonths(12).slice().reverse(); // más reciente primero
  return (
    <div className="field">
      <label>Mes</label>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        {months.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
      </select>
    </div>
  );
}

export function parseMonthKey(key: string): { year: number; month: number } {
  const [y, m] = key.split("-").map(Number);
  return { year: y, month: m - 1 };
}
