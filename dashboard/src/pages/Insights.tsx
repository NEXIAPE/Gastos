import { useEffect, useState } from "react";
import { fetchSpend, fetchSpendSince } from "../lib/queries";
import { byCategory, limaMonthKey, sumByGroup, sumPen } from "../lib/aggregate";
import { currentLimaYearMonth, monthRange } from "../lib/time";
import { soles } from "../lib/format";
import type { Transaction } from "../lib/types";

interface Tip { icon: string; title: string; body: string; tone?: "ok" | "warn" }

const TONE_COLOR: Record<string, string> = { ok: "#16a34a", warn: "#d97706" };

function buildTips(spend: Transaction[], prevSpend: Transaction[], hist: Transaction[]): Tip[] {
  const total = sumPen(spend);
  if (spend.length === 0) {
    return [{ icon: "📭", title: "Aún no hay gastos este mes",
      body: "Cuando entren tus consumos, aquí verás recomendaciones basadas en tu propia data." }];
  }
  const tips: Tip[] = [];

  // vs mes anterior
  const prevTotal = sumPen(prevSpend);
  if (prevTotal > 0) {
    const d = total - prevTotal;
    const ratio = Math.round((Math.abs(d) / prevTotal) * 100);
    tips.push({
      icon: d > 0 ? "📈" : "📉",
      title: `Llevas ${soles(total)} este mes`,
      body: `Es ${ratio}% ${d >= 0 ? "más" : "menos"} que el mes pasado (${soles(prevTotal)}).`,
      tone: d > 0 ? "warn" : "ok",
    });
  }

  // vs promedio histórico
  const monthly = new Map<string, number>();
  for (const r of hist) {
    const k = limaMonthKey(r.occurred_at);
    monthly.set(k, (monthly.get(k) ?? 0) + (r.amount_pen ?? 0));
  }
  const vals = [...monthly.values()].filter((v) => v > 0);
  if (vals.length >= 2) {
    const avg = vals.reduce((a, b) => a + b, 0) / vals.length;
    if (total > avg * 1.1) {
      tips.push({ icon: "⚠️", title: "Por encima de tu promedio",
        body: `Tu promedio mensual es ${soles(avg)} y este mes vas en ${soles(total)}.`, tone: "warn" });
    }
  }

  // top categoría (ignorando Sin categoría)
  const cats = byCategory(spend).filter((c) => c.key !== "Sin categoría");
  if (cats[0]) {
    tips.push({ icon: "🏆", title: `Tu mayor gasto: ${cats[0].key}`,
      body: `${soles(cats[0].value)} — ${Math.round((cats[0].value / total) * 100)}% de tu mes.` });
  }

  // Lifestyle
  const life = sumByGroup(spend, "Lifestyle");
  if (life > 0) {
    const p = Math.round((life / total) * 100);
    tips.push({ icon: "🍔", title: `Lifestyle: ${soles(life)} (${p}%)`,
      body: p >= 30
        ? "Es una porción grande del mes. Cocinar un par de noches o bajar el delivery te ahorraría bastante."
        : "Comer fuera, delivery, antojos, salidas, entretenimiento y viajes.",
      tone: p >= 30 ? "warn" : undefined });
  }

  // sin categorizar
  const sc = spend.filter((r) => r.category === "Sin categoría");
  if (sc.length > 0) {
    tips.push({ icon: "🏷️", title: `${soles(sumPen(sc))} sin categorizar`,
      body: `Tienes ${sc.length} movimiento(s) sin categoría. Clasifícalos en Transacciones → "Por revisar" para que tus números sean exactos.`,
      tone: "warn" });
  }

  // gastos hormiga (mismo comercio 3+ veces)
  const counts = new Map<string, { n: number; sum: number }>();
  for (const r of spend) {
    const k = r.merchant_clean || "—";
    const c = counts.get(k) ?? { n: 0, sum: 0 };
    c.n += 1; c.sum += r.amount_pen ?? 0; counts.set(k, c);
  }
  const hormiga = [...counts.entries()].filter(([, c]) => c.n >= 3).sort((a, b) => b[1].sum - a[1].sum)[0];
  if (hormiga) {
    tips.push({ icon: "🐜", title: `Gastos hormiga en ${hormiga[0]}`,
      body: `${hormiga[1].n} compras suman ${soles(hormiga[1].sum)} este mes. Los pequeños repetidos se acumulan.` });
  }

  // suscripciones / recurrentes
  const subs = [...new Set(spend.filter((r) => r.is_recurring).map((r) => r.merchant_clean))].filter(Boolean) as string[];
  if (subs.length > 0) {
    tips.push({ icon: "🔁", title: `${subs.length} suscripción(es): ${soles(sumPen(spend.filter((r) => r.is_recurring)))}`,
      body: `${subs.join(", ")}. Revisa si las usas todas; cancelar una que no uses es ahorro fijo cada mes.` });
  }

  // gastos fijos
  const fijo = sumByGroup(spend, "Fijo");
  if (fijo > 0) {
    tips.push({ icon: "🏠", title: `Gastos fijos: ${soles(fijo)}`,
      body: `${Math.round((fijo / total) * 100)}% de tu mes son fijos (vivienda, servicios, suscripciones, impuestos).` });
  }

  return tips;
}

export default function Insights() {
  const now = currentLimaYearMonth();
  const [tips, setTips] = useState<Tip[]>([]);
  const [label, setLabel] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const cur = monthRange(now.year, now.month);
    setLabel(cur.label);
    const prev = monthRange(now.month === 0 ? now.year - 1 : now.year, now.month === 0 ? 11 : now.month - 1);
    let hy = now.year, hm = now.month - 5;
    while (hm < 0) { hm += 12; hy -= 1; }
    const histStart = monthRange(hy, hm).start;

    const [spend, prevSpend, hist] = await Promise.all([
      fetchSpend(cur.start, cur.end), fetchSpend(prev.start, prev.end), fetchSpendSince(histStart),
    ]);
    setTips(buildTips(spend, prevSpend, hist));
    setLoading(false);
  }
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <div className="page-head">
        <h1 className="page">Recomendaciones</h1>
        <button className="primary" onClick={load} disabled={loading}>
          {loading ? "Analizando…" : "Actualizar"}
        </button>
      </div>
      <p className="muted">Análisis automático de tu data · {label} <span style={{ opacity: .7 }}>(sin IA)</span></p>

      {loading ? <p className="muted">Cargando…</p> : (
        <div className="tips">
          {tips.map((t, i) => (
            <div key={i} className="card tip" style={t.tone ? { borderLeftColor: TONE_COLOR[t.tone] } : undefined}>
              <div className="tip-title"><span className="tip-icon">{t.icon}</span>{t.title}</div>
              <div className="tip-body">{t.body}</div>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
