import { useEffect, useState } from "react";
import { deleteBudget, fetchBudgets, fetchSpend, fetchSpendSince, upsertBudget } from "../lib/queries";
import { limaMonthKey, sumByCategory } from "../lib/aggregate";
import { currentLimaYearMonth, monthRange } from "../lib/time";
import { soles } from "../lib/format";
import { GROUP_COLOR } from "../lib/types";
import { groupOf } from "../lib/categories";
import type { Budget, Transaction } from "../lib/types";

export default function Presupuestos() {
  const now = currentLimaYearMonth();
  const [spend, setSpend] = useState<Transaction[]>([]);
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [suggested, setSuggested] = useState<Record<string, number>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [label, setLabel] = useState("");
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const cur = monthRange(now.year, now.month);
    setLabel(cur.label);
    let sy = now.year, sm = now.month - 6;
    while (sm < 0) { sm += 12; sy -= 1; }
    const histStart = monthRange(sy, sm).start;

    const [s, b, hist] = await Promise.all([
      fetchSpend(cur.start, cur.end), fetchBudgets(), fetchSpendSince(histStart),
    ]);
    setSpend(s);
    setBudgets(b);

    // Sugerido = promedio mensual por categoría en los meses previos (sin el actual).
    const months = new Set<string>();
    const byCat = new Map<string, number>();
    for (const r of hist) {
      if (r.occurred_at >= cur.start) continue;
      months.add(limaMonthKey(r.occurred_at));
      byCat.set(r.category, (byCat.get(r.category) ?? 0) + (r.amount_pen ?? 0));
    }
    const n = Math.max(months.size, 1);
    const sug: Record<string, number> = {};
    for (const [cat, sum] of byCat) sug[cat] = Number((sum / n).toFixed(2));
    setSuggested(sug);
    setLoading(false);
  }
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const budgetMap: Record<string, number> = Object.fromEntries(budgets.map((b) => [b.category, b.amount_pen]));
  const cats = [...new Set([
    ...spend.map((r) => r.category),
    ...budgets.map((b) => b.category),
    ...Object.keys(suggested),
  ])].filter((c) => c !== "Sin categoría").sort((a, b) => sumByCategory(spend, b) - sumByCategory(spend, a));

  async function save(cat: string, value: number) {
    if (!Number.isFinite(value) || value <= 0) return;
    await upsertBudget(cat, Number(value.toFixed(2)));
    load();
  }

  return (
    <>
      <h1 className="page">Presupuestos</h1>
      <p className="muted">
        Define cuánto quieres gastar por categoría al mes ({label}). El sugerido es tu
        promedio de los últimos meses. Es informativo: no te bloquea nada.
      </p>

      {loading ? <p className="muted">Cargando…</p> : cats.length === 0 ? (
        <div className="card"><p className="muted">Aún no hay gastos para sugerir presupuestos.</p></div>
      ) : (
        <div className="budgets">
          {cats.map((cat) => {
            const spent = sumByCategory(spend, cat);
            const budget = budgetMap[cat];
            const sug = suggested[cat] ?? 0;
            const ratio = budget ? spent / budget : 0;
            const color = !budget ? "#cbd5e1" : ratio > 1 ? "#dc2626" : ratio >= 0.8 ? "#d97706" : "#16a34a";
            return (
              <div key={cat} className="card budget">
                <div className="budget-head">
                  <span className="dot" style={{ background: GROUP_COLOR[groupOf(cat)] }} />
                  <b>{cat}</b>
                  <span className="budget-amounts">
                    {soles(spent)}{budget ? <span className="muted"> / {soles(budget)}</span> : ""}
                  </span>
                </div>

                {budget ? (
                  <>
                    <div className="bbar"><div className="bbar-fill" style={{ width: `${Math.min(ratio * 100, 100)}%`, background: color }} /></div>
                    <div className="budget-foot">
                      <span className={ratio > 1 ? "neg" : "muted"}>
                        {ratio > 1 ? `Te pasaste ${soles(spent - budget)}` : `Te queda ${soles(budget - spent)}`}
                        {" "}· {Math.round(ratio * 100)}%
                      </span>
                      <span>
                        <button className="link" onClick={() => { const v = prompt(`Nuevo presupuesto para ${cat} (S/):`, String(budget)); if (v) save(cat, Number(v)); }}>editar</button>
                        {" · "}
                        <button className="link" onClick={async () => { await deleteBudget(cat); load(); }}>quitar</button>
                      </span>
                    </div>
                  </>
                ) : (
                  <div className="budget-foot">
                    <span className="muted">Sin presupuesto{sug > 0 ? ` · sugerido ${soles(sug)}` : ""}</span>
                    <span style={{ display: "flex", gap: 6 }}>
                      <input
                        type="number" step="0.01" placeholder="S/" style={{ width: 90 }}
                        value={drafts[cat] ?? ""} onChange={(e) => setDrafts({ ...drafts, [cat]: e.target.value })}
                      />
                      <button className="primary" onClick={() => save(cat, Number(drafts[cat]))}>Fijar</button>
                      {sug > 0 && <button onClick={() => save(cat, sug)}>Usar sugerido</button>}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </>
  );
}
