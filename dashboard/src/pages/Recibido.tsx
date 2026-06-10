import { useEffect, useState } from "react";
import { fetchReceived } from "../lib/queries";
import { currentLimaYearMonth, monthRange } from "../lib/time";
import { soles } from "../lib/format";
import { sumPen } from "../lib/aggregate";
import MonthPicker, { parseMonthKey } from "../components/MonthPicker";
import TxnTable from "../components/TxnTable";
import type { Transaction } from "../lib/types";

export default function Recibido() {
  const init = currentLimaYearMonth();
  const [monthKey, setMonthKey] = useState(`${init.year}-${String(init.month + 1).padStart(2, "0")}`);
  const [rows, setRows] = useState<Transaction[]>([]);

  function load() {
    const { year, month } = parseMonthKey(monthKey);
    const { start, end } = monthRange(year, month);
    fetchReceived(start, end).then(setRows);
  }
  useEffect(load, [monthKey]);

  return (
    <>
      <h1 className="page">Dinero recibido</h1>
      <p className="muted">Movimientos entrantes. No cuentan como gasto en ningún total.</p>
      <MonthPicker value={monthKey} onChange={setMonthKey} />
      <div className="card">
        <h2>Total recibido</h2>
        <div className="stat pos">{soles(sumPen(rows))}</div>
      </div>
      <div className="card"><TxnTable rows={rows} onChange={load} /></div>
    </>
  );
}
