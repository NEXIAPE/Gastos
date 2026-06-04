import { useEffect, useState } from "react";
import { fetchSpend } from "../lib/queries";
import { byMerchant } from "../lib/aggregate";
import { currentLimaYearMonth, monthRange } from "../lib/time";
import { soles } from "../lib/format";
import { Bars } from "../components/Charts";
import MonthPicker, { parseMonthKey } from "../components/MonthPicker";
import type { Slice } from "../lib/aggregate";

export default function TopComercios() {
  const init = currentLimaYearMonth();
  const [monthKey, setMonthKey] = useState(`${init.year}-${String(init.month + 1).padStart(2, "0")}`);
  const [data, setData] = useState<Slice[]>([]);

  useEffect(() => {
    const { year, month } = parseMonthKey(monthKey);
    const { start, end } = monthRange(year, month);
    fetchSpend(start, end).then((rows) => setData(byMerchant(rows).slice(0, 15)));
  }, [monthKey]);

  return (
    <>
      <h1 className="page">Top comercios</h1>
      <MonthPicker value={monthKey} onChange={setMonthKey} />
      <div className="card">
        <Bars data={data} color="#7c3aed" horizontal />
      </div>
      <div className="card">
        <table>
          <thead><tr><th>Comercio</th><th className="num">Gasto</th></tr></thead>
          <tbody>
            {data.map((d) => (
              <tr key={d.key}><td>{d.key}</td><td className="num">{soles(d.value)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
