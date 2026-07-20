import { useEffect, useState } from "react";
import {
  addRule, bulkRecategorize, deleteAllTransactions, deleteRule, fetchRules,
  getFxRate, getSelfNames, insertManual, setFxRate, setSelfNames,
} from "../lib/queries";
import { supabase } from "../lib/supabase";
import { CHANNELS, CHANNEL_LABEL, EXPENSE_GROUPS, type CategoryRule, type ExpenseGroup } from "../lib/types";
import { addCategory, deleteCategory, useCategories } from "../lib/categories";
import { localInputToLimaIso } from "../lib/time";
import { parseCsv } from "../lib/csv";

export default function Ajustes() {
  return (
    <>
      <h1 className="page">Ajustes</h1>
      <FxCard />
      <SelfNamesCard />
      <CategoriesCard />
      <ManualCard />
      <RulesCard />
      <BulkCard />
      <ImportCard />
      <DangerCard />
    </>
  );
}

function CategoriesCard() {
  const { categories, loading, reload } = useCategories();
  const [name, setName] = useState("");
  const [group, setGroup] = useState<ExpenseGroup>("Lifestyle");
  const [msg, setMsg] = useState<string | null>(null);

  async function add() {
    if (!name.trim()) return;
    setMsg(null);
    try {
      await addCategory(name, group);
      setName("");
      setMsg("Agregada ✓");
    } catch (e) { setMsg(String(e)); }
  }

  async function remove(cat: string) {
    if (!confirm(`¿Borrar la categoría "${cat}"? Las transacciones que ya la tienen la conservan como texto.`)) return;
    try { await deleteCategory(cat); } catch (e) { setMsg(String(e)); }
  }

  return (
    <div className="card">
      <h2>Categorías</h2>
      <p className="muted">Agrega las categorías que necesites; aparecen al toque en toda la app y en el correo diario.</p>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div className="field"><label>Nueva categoría</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="ej. Belleza" /></div>
        <div className="field"><label>Tipo de gasto</label>
          <select value={group} onChange={(e) => setGroup(e.target.value as ExpenseGroup)}>
            {EXPENSE_GROUPS.map((g) => <option key={g}>{g}</option>)}</select></div>
        <button className="primary" onClick={add}>Añadir</button>
        {msg && <span className="muted">{msg}</span>}
      </div>
      {!loading && (
        <div className="row" style={{ gap: 6, marginTop: 12 }}>
          {categories.map((c) => (
            <span key={c.name} className="badge">
              {c.name}
              {c.name !== "Sin categoría" && (
                <button className="link" style={{ marginLeft: 6, fontSize: 11 }} onClick={() => remove(c.name)}>✕</button>
              )}
            </span>
          ))}
        </div>
      )}
      <p className="muted" style={{ marginTop: 8, fontSize: 12 }}>
        {loading ? "Cargando…" : `${categories.length} categorías`}
        {" · "}<button className="link" onClick={() => reload()}>refrescar</button>
      </p>
    </div>
  );
}

function FxCard() {
  const [rate, setRate] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => { getFxRate().then((r) => setRate(String(r))); }, []);
  return (
    <div className="card">
      <h2>Tipo de cambio USD → PEN (fijo)</h2>
      <p className="muted">Se usa cuando un correo en dólares no trae el monto ya convertido a soles.</p>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div className="field"><label>Soles por dólar</label>
          <input type="number" step="0.01" value={rate} onChange={(e) => setRate(e.target.value)} /></div>
        <button className="primary" onClick={async () => {
          await setFxRate(Number(rate)); setSaved(true); setTimeout(() => setSaved(false), 1500);
        }}>Guardar</button>
        {saved && <span className="pos">Guardado</span>}
      </div>
    </div>
  );
}

function SelfNamesCard() {
  const [names, setNames] = useState("");
  const [saved, setSaved] = useState(false);
  useEffect(() => { getSelfNames().then((n) => setNames(n.join(", "))); }, []);
  return (
    <div className="card">
      <h2>Mis nombres (transferencias a mí mismo)</h2>
      <p className="muted">
        Cuando un Yape/Plin llega a uno de estos nombres (ej. tu propio Plin), se marca como
        transferencia y no cuenta como gasto. Sepáralos por coma; usa el nombre tal como
        aparece en tus correos (ej. "Juana Perez").
      </p>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div className="field" style={{ flex: 1 }}>
          <label>Nombres / alias</label>
          <input value={names} style={{ width: "100%" }} onChange={(e) => setNames(e.target.value)}
            placeholder="Tu Nombre Apellido, Apodo" />
        </div>
        <button className="primary" onClick={async () => {
          await setSelfNames(names.split(",").map((n) => n.trim()).filter(Boolean));
          setSaved(true); setTimeout(() => setSaved(false), 1500);
        }}>Guardar</button>
        {saved && <span className="pos">Guardado</span>}
      </div>
    </div>
  );
}

function ManualCard() {
  const { names: categoryNames } = useCategories();
  const [merchant, setMerchant] = useState("");
  const [amount, setAmount] = useState("");
  const [currency, setCurrency] = useState("PEN");
  const [direction, setDirection] = useState("out");
  const [channel, setChannel] = useState("efectivo");
  const [category, setCategory] = useState("Sin categoría");
  const [when, setWhen] = useState("");
  const [notes, setNotes] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  async function add() {
    setMsg(null);
    try {
      const amt = Number(amount);
      let amountPen = amt;
      if (currency === "USD") amountPen = Number((amt * (await getFxRate())).toFixed(2));
      await insertManual({
        merchant_raw: merchant, merchant_clean: merchant.toUpperCase(),
        amount: amt, amount_pen: amountPen, currency: currency as "PEN" | "USD",
        direction: direction as "out" | "in" | "transfer",
        status: "confirmed", category,
        channel: channel as "efectivo", source: "manual",
        occurred_at: when ? localInputToLimaIso(when) : new Date().toISOString(),
        notes: notes || null,
      });
      setMsg("Agregada ✓");
      setMerchant(""); setAmount(""); setNotes("");
    } catch (e) { setMsg(String(e)); }
  }

  return (
    <div className="card">
      <h2>Agregar transacción manual</h2>
      <p className="muted">Para efectivo y yapeos pequeños (&lt; S/10) que no generan correo.</p>
      <div className="row">
        <div className="field" style={{ flex: 2 }}><label>Comercio / descripción</label>
          <input value={merchant} style={{ width: "100%" }} onChange={(e) => setMerchant(e.target.value)} /></div>
        <div className="field"><label>Monto</label>
          <input type="number" step="0.01" value={amount} onChange={(e) => setAmount(e.target.value)} /></div>
        <div className="field"><label>Moneda</label>
          <select value={currency} onChange={(e) => setCurrency(e.target.value)}>
            <option>PEN</option><option>USD</option></select></div>
      </div>
      <div className="row">
        <div className="field"><label>Dirección</label>
          <select value={direction} onChange={(e) => setDirection(e.target.value)}>
            <option value="out">out (gasto)</option><option value="in">in (recibido)</option>
            <option value="transfer">transfer</option></select></div>
        <div className="field"><label>Canal</label>
          <select value={channel} onChange={(e) => setChannel(e.target.value)}>
            {CHANNELS.map((c) => <option key={c} value={c}>{CHANNEL_LABEL[c]}</option>)}</select></div>
        <div className="field"><label>Categoría</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {categoryNames.map((c) => <option key={c}>{c}</option>)}</select></div>
        <div className="field"><label>Fecha/hora</label>
          <input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} /></div>
      </div>
      <div className="field"><label>Notas</label>
        <input value={notes} style={{ width: "100%" }} onChange={(e) => setNotes(e.target.value)} /></div>
      <button className="primary" onClick={add}>Agregar</button>
      {msg && <span className="muted" style={{ marginLeft: 10 }}>{msg}</span>}
    </div>
  );
}

function RulesCard() {
  const { names: categoryNames } = useCategories();
  const [rules, setRules] = useState<CategoryRule[]>([]);
  const [match, setMatch] = useState("");
  const [category, setCategory] = useState("Sin categoría");
  const [priority, setPriority] = useState("10");
  function load() { fetchRules().then(setRules); }
  useEffect(load, []);

  return (
    <div className="card">
      <h2>Reglas de categorización</h2>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div className="field"><label>Texto en comercio</label>
          <input value={match} onChange={(e) => setMatch(e.target.value)} placeholder="RAPPI" /></div>
        <div className="field"><label>Categoría</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {categoryNames.map((c) => <option key={c}>{c}</option>)}</select></div>
        <div className="field"><label>Prioridad</label>
          <input type="number" value={priority} style={{ width: 80 }}
            onChange={(e) => setPriority(e.target.value)} /></div>
        <button className="primary" onClick={async () => {
          if (!match.trim()) return;
          await addRule(match.trim(), category, Number(priority)); setMatch(""); load();
        }}>Añadir</button>
      </div>
      <div className="table-scroll" style={{ marginTop: 12 }}>
      <table>
        <thead><tr><th>Texto</th><th>Categoría</th><th className="num">Prioridad</th><th></th></tr></thead>
        <tbody>
          {rules.map((r) => (
            <tr key={r.id}>
              <td>{r.match_text}</td><td>{r.category}</td><td className="num">{r.priority}</td>
              <td><button className="link" onClick={async () => { await deleteRule(r.id); load(); }}>borrar</button></td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
    </div>
  );
}

function BulkCard() {
  const { names: categoryNames } = useCategories();
  const [match, setMatch] = useState("");
  const [category, setCategory] = useState("Sin categoría");
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="card">
      <h2>Recategorización masiva</h2>
      <p className="muted">Reasigna todas las transacciones cuyo comercio contenga el texto.</p>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div className="field"><label>Comercio contiene</label>
          <input value={match} onChange={(e) => setMatch(e.target.value)} placeholder="RAPPI" /></div>
        <div className="field"><label>Nueva categoría</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            {categoryNames.map((c) => <option key={c}>{c}</option>)}</select></div>
        <button className="primary" onClick={async () => {
          if (!match.trim()) return;
          await bulkRecategorize(match.trim(), category); setMsg("Listo ✓"); setMatch("");
        }}>Aplicar</button>
        {msg && <span className="pos">{msg}</span>}
      </div>
    </div>
  );
}

function ImportCard() {
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true); setMsg(null);
    try {
      const rows = parseCsv(await file.text());
      const fx = await getFxRate();
      const payload = rows.map((r) => {
        const amount = Number(r.amount ?? r.monto ?? 0);
        const currency = (r.currency ?? "PEN").toUpperCase() === "USD" ? "USD" : "PEN";
        const amount_pen = r.amount_pen ? Number(r.amount_pen)
          : currency === "USD" ? Number((amount * fx).toFixed(2)) : amount;
        return {
          occurred_at: r.occurred_at || r.fecha || new Date().toISOString(),
          merchant_raw: r.merchant_raw ?? r.merchant_clean ?? r.comercio ?? "",
          merchant_clean: (r.merchant_clean ?? r.comercio ?? "").toUpperCase(),
          amount, currency: currency as "PEN" | "USD", amount_pen,
          direction: (r.direction || "out") as "out" | "in" | "transfer",
          status: (r.status || "confirmed") as "confirmed",
          category: r.category || "Sin categoría",
          channel: (r.channel || null) as "tarjeta" | null,
          card_label: r.card_label || null,
          counterparty: r.counterparty || null,
          notes: r.notes || null,
          source: "import",
        };
      });
      // Inserta en lotes de 200.
      for (let i = 0; i < payload.length; i += 200) {
        const { error } = await supabase.from("transactions").insert(payload.slice(i, i + 200));
        if (error) throw error;
      }
      setMsg(`Importadas ${payload.length} transacciones ✓`);
    } catch (err) { setMsg(`Error: ${String(err)}`); }
    finally { setBusy(false); e.target.value = ""; }
  }

  return (
    <div className="card">
      <h2>Carga inicial de histórico (CSV)</h2>
      <p className="muted">
        Columnas reconocidas: occurred_at, merchant_clean, amount, currency, amount_pen,
        direction, status, category, channel, card_label, counterparty, notes.
      </p>
      <input type="file" accept=".csv" onChange={onFile} disabled={busy} />
      {msg && <p className="muted">{msg}</p>}
    </div>
  );
}

function DangerCard() {
  const [confirm1, setConfirm1] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  return (
    <div className="card" style={{ borderColor: "#fecaca" }}>
      <h2 style={{ color: "var(--danger)" }}>Zona de peligro</h2>
      <p className="muted">Borra TODAS tus transacciones (las reglas y ajustes se conservan).</p>
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div className="field"><label>Escribe BORRAR para confirmar</label>
          <input value={confirm1} onChange={(e) => setConfirm1(e.target.value)} /></div>
        <button className="danger" disabled={confirm1 !== "BORRAR"} onClick={async () => {
          await deleteAllTransactions(); setMsg("Todas las transacciones fueron borradas."); setConfirm1("");
        }}>Borrar todo</button>
      </div>
      {msg && <p className="neg">{msg}</p>}
    </div>
  );
}
