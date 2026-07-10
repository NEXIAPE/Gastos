import { useState } from "react";
import type { Transaction } from "../lib/types";
import { CHANNELS, CHANNEL_LABEL, DIRECTIONS, STATUSES } from "../lib/types";
import { useCategories } from "../lib/categories";
import { addRule, deleteTransaction, updateTransaction } from "../lib/queries";

export default function EditTxnModal({
  txn, onClose, onSaved,
}: { txn: Transaction; onClose: () => void; onSaved: () => void }) {
  const { names: categoryNames } = useCategories();
  const [category, setCategory] = useState(txn.category);
  const [direction, setDirection] = useState(txn.direction);
  const [status, setStatus] = useState(txn.status);
  const [channel, setChannel] = useState(txn.channel ?? "");
  const [merchant, setMerchant] = useState(txn.merchant_clean ?? "");
  const [amountPen, setAmountPen] = useState(String(txn.amount_pen ?? txn.amount));
  const [notes, setNotes] = useState(txn.notes ?? "");
  const [tags, setTags] = useState((txn.tags ?? []).join(", "));
  const [makeRule, setMakeRule] = useState(false);
  const [ruleText, setRuleText] = useState(txn.merchant_clean ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function save() {
    setBusy(true); setErr(null);
    try {
      await updateTransaction(txn.id, {
        category, direction, status,
        channel: (channel || null) as Transaction["channel"],
        merchant_clean: merchant,
        amount_pen: Number(amountPen),
        notes: notes || null,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      if (makeRule && ruleText.trim()) {
        await addRule(ruleText.trim(), category, 100); // alta prioridad: la creó el usuario
      }
      onSaved();
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!confirm("¿Borrar esta transacción?")) return;
    setBusy(true);
    try { await deleteTransaction(txn.id); onSaved(); }
    catch (e) { setErr(String(e)); } finally { setBusy(false); }
  }

  return (
    <div className="modal-bg" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h2>Editar transacción</h2>
        <p className="muted" style={{ marginTop: -6 }}>{txn.merchant_raw}</p>

        <div className="field">
          <label>Comercio (normalizado)</label>
          <input value={merchant} style={{ width: "100%" }} onChange={(e) => setMerchant(e.target.value)} />
        </div>

        <div className="row">
          <div className="field" style={{ flex: 1 }}>
            <label>Categoría</label>
            <select value={category} style={{ width: "100%" }} onChange={(e) => setCategory(e.target.value)}>
              {categoryNames.map((c) => <option key={c}>{c}</option>)}
            </select>
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label>Monto (S/)</label>
            <input type="number" step="0.01" value={amountPen} style={{ width: "100%" }}
              onChange={(e) => setAmountPen(e.target.value)} />
          </div>
        </div>

        <div className="row">
          <div className="field" style={{ flex: 1 }}>
            <label>Dirección</label>
            <select value={direction} style={{ width: "100%" }}
              onChange={(e) => setDirection(e.target.value as Transaction["direction"])}>
              {DIRECTIONS.map((d) => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label>Estado</label>
            <select value={status} style={{ width: "100%" }}
              onChange={(e) => setStatus(e.target.value as Transaction["status"])}>
              {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="field" style={{ flex: 1 }}>
            <label>Canal</label>
            <select value={channel} style={{ width: "100%" }} onChange={(e) => setChannel(e.target.value)}>
              <option value="">—</option>
              {CHANNELS.map((c) => <option key={c} value={c}>{CHANNEL_LABEL[c]}</option>)}
            </select>
          </div>
        </div>

        <div className="field">
          <label>Notas</label>
          <input value={notes} style={{ width: "100%" }} onChange={(e) => setNotes(e.target.value)} />
        </div>
        <div className="field">
          <label>Etiquetas (separadas por coma)</label>
          <input value={tags} style={{ width: "100%" }} onChange={(e) => setTags(e.target.value)}
            placeholder="viaje, reembolsable" />
        </div>

        <div className="field">
          <label>
            <input type="checkbox" checked={makeRule} onChange={(e) => setMakeRule(e.target.checked)} />{" "}
            Crear regla a partir de esta transacción
          </label>
          {makeRule && (
            <input value={ruleText} style={{ width: "100%", marginTop: 6 }}
              onChange={(e) => setRuleText(e.target.value)}
              placeholder="Texto a buscar en el comercio (ej. RAPPI)" />
          )}
        </div>

        {err && <p className="neg">{err}</p>}
        <div className="row" style={{ justifyContent: "space-between", marginTop: 8 }}>
          <button className="danger" onClick={remove} disabled={busy}>Borrar</button>
          <div style={{ display: "flex", gap: 8 }}>
            <button onClick={onClose} disabled={busy}>Cancelar</button>
            <button className="primary" onClick={save} disabled={busy}>Guardar</button>
          </div>
        </div>
      </div>
    </div>
  );
}
