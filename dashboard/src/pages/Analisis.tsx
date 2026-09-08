import { useEffect, useState } from "react";
import { fetchSpend, fetchSpendSince } from "../lib/queries";
import { byCategory, byChannel, byGroup, byMerchant, limaMonthKey, type Slice } from "../lib/aggregate";
import { currentLimaYearMonth, lastNMonths, monthRange } from "../lib/time";
import { CHANNEL_LABEL } from "../lib/types";
import { Bars, CategoryBars } from "../components/Charts";
import GroupBar from "../components/GroupBar";
import MonthPicker, { parseMonthKey } from "../components/MonthPicker";
import type { Transaction } from "../lib/types";

export default function Analisis() {
  const init = currentLimaYearMonth();
  const [monthKey, setMonthKey] = useState(`${init.year}-${String(init.month + 1).padStart(2, "0")}`);
  const [rows, setRows] = useState<Transaction[]>([]);
  const [trend, setTrend] = useState<Slice[]>([]);

  useEffect(() => {
    const { year, month } = parseMonthKey(monthKey);
    const { start, end } = monthRange(year, month);
    fetchSpend(start, end).then(setRows);
  }, [monthKey]);

  useEffect(() => {
    const months = lastNMonths(12);
    const startIso = monthRange(months[0].year, months[0].month).start;
    fetchSpendSince(startIso).then((rs) => {
      const totals = new Map<string, number>();
      for (const r of rs) {
        const k = limaMonthKey(r.occurred_at);
        totals.set(k, (totals.get(k) ?? 0) + (r.amount_pen ?? 0));
      }
      setTrend(months.map((m) => ({ key: m.label, value: Number((totals.get(m.key) ?? 0).toFixed(2)) })));
    });
  }, []);

  const channelData = byChannel(rows).map((s) => ({ key: CHANNEL_LABEL[s.key] ?? s.key, value: s.value }));

  return (
    <>
      <div className="page-head">
        <h1 className="page">Análisis</h1>
        <MonthPicker value={monthKey} onChange={setMonthKey} />
      </div>

      <div className="card">
        <h2>Tendencia mensual · últimos 12 meses</h2>
        <Bars data={trend} />
      </div>

      <div className="card">
        <h2>Gasto por tipo · {monthKey}</h2>
        <GroupBar data={byGroup(rows)} />
      </div>

      <div className="grid-2">
        <div className="card">
          <h2>Por categoría</h2>
          <CategoryBars data={byCategory(rows)} />
        </div>
        <div className="card">
          <h2>Por canal de pago</h2>
          <Bars data={channelData} color="#0891b2" />
        </div>
      </div>

      <div className="card">
        <h2>Top comercios del mes</h2>
        <Bars data={byMerchant(rows).slice(0, 12)} color="#7c3aed" horizontal />
      </div>
    </>
  );
}
