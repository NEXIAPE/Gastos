import { useEffect, useState } from "react";
import { fetchSpendSince } from "../lib/queries";
import { limaMonthKey } from "../lib/aggregate";
import { lastNMonths, monthRange } from "../lib/time";
import { Bars } from "../components/Charts";
import type { Slice } from "../lib/aggregate";

export default function Tendencia() {
  const [data, setData] = useState<Slice[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      const months = lastNMonths(12);
      const startIso = monthRange(months[0].year, months[0].month).start;
      const rows = await fetchSpendSince(startIso);

      const totals = new Map<string, number>();
      for (const r of rows) {
        const k = limaMonthKey(r.occurred_at);
        totals.set(k, (totals.get(k) ?? 0) + (r.amount_pen ?? 0));
      }
      setData(months.map((m) => ({
        key: m.label,
        value: Number((totals.get(m.key) ?? 0).toFixed(2)),
      })));
      setLoading(false);
    })();
  }, []);

  return (
    <>
      <h1 className="page">Tendencia mensual (últimos 12 meses)</h1>
      <div className="card">
        {loading ? <p className="muted">Cargando…</p> : <Bars data={data} />}
      </div>
    </>
  );
}
