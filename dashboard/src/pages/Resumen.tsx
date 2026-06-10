import { useEffect, useState } from "react";
import { fetchRefunds, fetchSpend } from "../lib/queries";
import { byCategory, sumPen } from "../lib/aggregate";
import { currentLimaYearMonth, monthRange } from "../lib/time";
import { pct, soles } from "../lib/format";
import { Donut } from "../components/Charts";
import TxnTable from "../components/TxnTable";
import type { Transaction } from "../lib/types";

export default function Resumen() {
  const [rows, setRows] = useState<Transaction[]>([]);
  const [net, setNet] = useState(0);
  const [prevNet, setPrevNet] = useState(0);
  const [label, setLabel] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const { year, month } = currentLimaYearMonth();
    const cur = monthRange(year, month);
    const prev = monthRange(month === 0 ? year - 1 : year, month === 0 ? 11 : month - 1);
    setLabel(cur.label);

    const [spend, refunds, pSpend, pRefunds] = await Promise.all([
      fetchSpend(cur.start, cur.end), fetchRefunds(cur.start, cur.end),
      fetchSpend(prev.start, prev.end), fetchRefunds(prev.start, prev.end),
    ]);
    setRows(spend);
    setNet(sumPen(spend) - sumPen(refunds));
    setPrevNet(sumPen(pSpend) - sumPen(pRefunds));
    setLoading(false);
  }
  useEffect(() => { load(); }, []);

  const diff = net - prevNet;

  return (
    <>
      <h1 className="page">Resumen — {label}</h1>
      {loading ? <p className="muted">Cargando…</p> : (
        <>
          <div className="row">
            <div className="card" style={{ flex: 1, minWidth: 220 }}>
              <h2>Gasto del mes (neto)</h2>
              <div className="stat">{soles(net)}</div>
              <div className="stat-sub">
                vs mes anterior {soles(prevNet)}{" "}
                <span className={diff > 0 ? "neg" : "pos"}>({pct(net, prevNet)})</span>
              </div>
            </div>
            <div className="card" style={{ flex: 1, minWidth: 220 }}>
              <h2>Transacciones</h2>
              <div className="stat">{rows.length}</div>
              <div className="stat-sub">solo gastos confirmados</div>
            </div>
          </div>

          <div className="card">
            <h2>Gasto por categoría</h2>
            <Donut data={byCategory(rows)} />
          </div>

          <div className="card">
            <h2>Movimientos del mes</h2>
            <TxnTable rows={rows} onChange={load} />
          </div>
        </>
      )}
    </>
  );
}
