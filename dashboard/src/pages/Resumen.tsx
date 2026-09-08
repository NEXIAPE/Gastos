import { useEffect, useMemo, useState } from "react";
import { fetchRefunds, fetchSpend, fetchSpendSince } from "../lib/queries";
import { byCategory, byGroup, limaMonthKey, sumByCategory, sumByGroup, sumPen } from "../lib/aggregate";
import { currentLimaYearMonth, monthRange } from "../lib/time";
import { pct, soles } from "../lib/format";
import { CategoryBars } from "../components/Charts";
import GroupBar from "../components/GroupBar";
import KpiCard from "../components/KpiCard";
import TxnTable from "../components/TxnTable";
import type { Transaction } from "../lib/types";

export default function Resumen() {
  const now = currentLimaYearMonth();
  const [ym, setYm] = useState<{ year: number; month: number }>(now);
  const [rows, setRows] = useState<Transaction[]>([]);
  const [refunds, setRefunds] = useState<Transaction[]>([]);
  const [prevNet, setPrevNet] = useState(0);
  const [avgMonthly, setAvgMonthly] = useState(0);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const cur = monthRange(ym.year, ym.month);
    const prev = monthRange(ym.month === 0 ? ym.year - 1 : ym.year, ym.month === 0 ? 11 : ym.month - 1);

    // Inicio de la ventana de 12 meses (para el promedio mensual).
    let hy = now.year, hm = now.month - 11;
    while (hm < 0) { hm += 12; hy -= 1; }
    const histStart = monthRange(hy, hm).start;

    const [spend, refs, pSpend, pRefs, hist] = await Promise.all([
      fetchSpend(cur.start, cur.end), fetchRefunds(cur.start, cur.end),
      fetchSpend(prev.start, prev.end), fetchRefunds(prev.start, prev.end),
      fetchSpendSince(histStart),
    ]);

    setRows(spend);
    setRefunds(refs);
    setPrevNet(sumPen(pSpend) - sumPen(pRefs));

    // Promedio mensual de los últimos 12 meses (solo meses con datos).
    const totals = new Map<string, number>();
    for (const t of hist) {
      const k = limaMonthKey(t.occurred_at);
      totals.set(k, (totals.get(k) ?? 0) + (t.amount_pen ?? 0));
    }
    const vals = [...totals.values()].filter((v) => v > 0);
    setAvgMonthly(vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : 0);

    setLoading(false);
  }
  useEffect(() => { load(); }, [ym]); // eslint-disable-line react-hooks/exhaustive-deps

  const net = sumPen(rows) - sumPen(refunds);
  const diff = net - prevNet;
  const cats = useMemo(() => byCategory(rows), [rows]);
  const groups = useMemo(() => byGroup(rows), [rows]);
  const topCat = cats[0];

  const label = monthRange(ym.year, ym.month).label;
  const move = (delta: number) => {
    let y = ym.year, m = ym.month + delta;
    while (m < 0) { m += 12; y -= 1; }
    while (m > 11) { m -= 12; y += 1; }
    setYm({ year: y, month: m });
  };
  const isCurrent = ym.year === now.year && ym.month === now.month;

  return (
    <>
      <div className="page-head">
        <h1 className="page">Resumen</h1>
        <div className="month-nav">
          <button onClick={() => move(-1)} aria-label="Mes anterior">‹</button>
          <span className="month-label">{label}</span>
          <button onClick={() => move(1)} disabled={isCurrent} aria-label="Mes siguiente">›</button>
        </div>
      </div>

      {loading ? <p className="muted">Cargando…</p> : (
        <>
          <div className="kpi-grid">
            <KpiCard
              icon="💸" label="Gasto del mes" value={soles(net)} accent="#2563eb"
              sub={<>vs mes anterior {soles(prevNet)}{" "}
                <span className={diff > 0 ? "neg" : "pos"}>({pct(net, prevNet)})</span></>}
            />
            <KpiCard
              icon="📅" label="Promedio mensual" value={soles(avgMonthly)} accent="#64748b"
              sub="últimos 12 meses con datos"
            />
            <KpiCard
              icon="🍔" label="Lifestyle" value={soles(sumByGroup(rows, "Lifestyle"))} accent="#db2777"
              sub="comer fuera, delivery, antojos, salidas…"
            />
            <KpiCard
              icon="🛍️" label="Compras" value={soles(sumByGroup(rows, "Compras"))} accent="#d97706"
              sub="compras personales + hogar"
            />
            <KpiCard
              icon="🐶" label="Luna" value={soles(sumByCategory(rows, "Luna"))} accent="#16a34a"
              sub="comida y cosas de Luna"
            />
            <KpiCard
              icon="🏆" label="Mayor gasto" value={topCat ? topCat.key : "—"} accent="#7c3aed"
              sub={topCat ? soles(topCat.value) : "sin gastos aún"}
            />
          </div>

          <div className="card">
            <h2>Gasto por tipo</h2>
            <GroupBar data={groups} />
          </div>

          <div className="grid-2">
            <div className="card">
              <h2>Gasto por categoría</h2>
              <CategoryBars data={cats} />
            </div>
            <div className="card">
              <h2>Movimientos recientes</h2>
              <TxnTable rows={rows.slice(0, 8)} onChange={load} />
            </div>
          </div>
        </>
      )}
    </>
  );
}
