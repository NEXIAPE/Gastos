import { useEffect, useState } from "react";
import { fetchSpend } from "../lib/queries";
import { byChannel } from "../lib/aggregate";
import { currentLimaYearMonth, monthRange } from "../lib/time";
import { soles } from "../lib/format";
import { CHANNEL_LABEL } from "../lib/types";
import { Bars } from "../components/Charts";
import MonthPicker, { parseMonthKey } from "../components/MonthPicker";
import type { Slice } from "../lib/aggregate";

export default function PorCanal() {
  const init = currentLimaYearMonth();
  const [monthKey, setMonthKey] = useState(`${init.year}-${String(init.month + 1).padStart(2, "0")}`);
  const [data, setData] = useState<Slice[]>([]);

  useEffect(() => {
    const { year, month } = parseMonthKey(monthKey);
    const { start, end } = monthRange(year, month);
    fetchSpend(start, end).then((rows) =>
      setData(byChannel(rows).map((s) => ({ key: CHANNEL_LABEL[s.key] ?? s.key, value: s.value }))));
  }, [monthKey]);

  return (
    <>
      <h1 className="page">Gasto por canal</h1>
      <MonthPicker value={monthKey} onChange={setMonthKey} />
      <div className="card"><Bars data={data} color="#0891b2" /></div>
      <div className="card">
        <table>
          <thead><tr><th>Canal</th><th className="num">Gasto</th></tr></thead>
          <tbody>{data.map((d) => (
            <tr key={d.key}><td>{d.key}</td><td className="num">{soles(d.value)}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </>
  );
}
