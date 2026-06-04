import { useEffect, useMemo, useState } from "react";
import { fetchSpend } from "../lib/queries";
import { byCategory } from "../lib/aggregate";
import { currentLimaYearMonth, monthRange } from "../lib/time";
import { soles } from "../lib/format";
import { Bars } from "../components/Charts";
import MonthPicker, { parseMonthKey } from "../components/MonthPicker";
import TxnTable from "../components/TxnTable";
import type { Transaction } from "../lib/types";

export default function PorCategoria() {
  const init = currentLimaYearMonth();
  const [monthKey, setMonthKey] = useState(`${init.year}-${String(init.month + 1).padStart(2, "0")}`);
  const [rows, setRows] = useState<Transaction[]>([]);
  const [selected, setSelected] = useState<string | null>(null);

  function load() {
    const { year, month } = parseMonthKey(monthKey);
    const { start, end } = monthRange(year, month);
    fetchSpend(start, end).then(setRows);
  }
  useEffect(load, [monthKey]);

  const slices = useMemo(() => byCategory(rows), [rows]);
  const detail = selected ? rows.filter((r) => r.category === selected) : [];

  return (
    <>
      <h1 className="page">Por categoría</h1>
      <MonthPicker value={monthKey} onChange={(k) => { setMonthKey(k); setSelected(null); }} />
      <div className="card">
        <Bars data={slices} color="#16a34a" horizontal />
      </div>
      <div className="card">
        <h2>Selecciona una categoría</h2>
        <div className="row" style={{ gap: 8 }}>
          {slices.map((s) => (
            <button key={s.key} className={selected === s.key ? "primary" : ""}
              onClick={() => setSelected(s.key)}>
              {s.key} · {soles(s.value)}
            </button>
          ))}
        </div>
      </div>
      {selected && (
        <div className="card">
          <h2>{selected}</h2>
          <TxnTable rows={detail} onChange={load} />
        </div>
      )}
    </>
  );
}
