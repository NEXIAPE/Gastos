import { useState } from "react";
import type { Transaction } from "../lib/types";
import { CHANNEL_LABEL } from "../lib/types";
import { soles } from "../lib/format";
import { fmtDateTime } from "../lib/time";
import { deleteTransaction } from "../lib/queries";
import EditTxnModal from "./EditTxnModal";

function StatusBadge({ t }: { t: Transaction }) {
  if (t.status === "needs_review") return <span className="badge review">por revisar</span>;
  if (t.direction === "in") return <span className="badge in">recibido</span>;
  if (t.direction === "transfer") return <span className="badge transfer">transferencia</span>;
  if (t.status !== "confirmed") return <span className="badge">{t.status}</span>;
  return null;
}

export default function TxnTable({ rows, onChange }: { rows: Transaction[]; onChange: () => void }) {
  const [editing, setEditing] = useState<Transaction | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  if (rows.length === 0) return <p className="muted">No hay transacciones.</p>;

  async function quickDelete(t: Transaction) {
    const name = t.merchant_clean || t.merchant_raw || "esta transacción";
    if (!confirm(`¿Borrar "${name}" (${soles(t.amount_pen)})?`)) return;
    setBusyId(t.id);
    try { await deleteTransaction(t.id); onChange(); }
    catch (e) { alert(String(e)); }
    finally { setBusyId(null); }
  }

  return (
    <>
      <div className="table-scroll">
      <table className="txntable">
        <thead>
          <tr>
            <th>Fecha</th><th>Comercio</th><th>Categoría</th><th>Canal</th>
            <th className="num">Monto</th><th></th><th></th><th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((t) => (
            <tr key={t.id}>
              <td className="c-date">{fmtDateTime(t.occurred_at)}</td>
              <td className="c-merchant">
                {t.merchant_clean || t.merchant_raw || "—"}
                {t.is_recurring && <span className="badge" style={{ marginLeft: 6 }}>recurrente</span>}
              </td>
              <td className="c-cat">{t.category}</td>
              <td className="c-chan">{t.channel ? CHANNEL_LABEL[t.channel] : "—"}</td>
              <td className="num c-amount">
                {soles(t.amount_pen)}
                {t.currency === "USD" && <div className="stat-sub">US$ {t.amount.toFixed(2)}</div>}
              </td>
              <td className="c-status"><StatusBadge t={t} /></td>
              <td className="c-edit"><button className="link" onClick={() => setEditing(t)}>editar</button></td>
              <td className="c-delete">
                <button className="link" style={{ color: "var(--danger)" }} disabled={busyId === t.id}
                  onClick={() => quickDelete(t)}>
                  {busyId === t.id ? "…" : "borrar"}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>
      {editing && (
        <EditTxnModal
          txn={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); onChange(); }}
        />
      )}
    </>
  );
}
