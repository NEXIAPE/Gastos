import { useEffect, useState } from "react";
import { fetchNeedsReview } from "../lib/queries";
import TxnTable from "../components/TxnTable";
import type { Transaction } from "../lib/types";

export default function PorRevisar() {
  const [rows, setRows] = useState<Transaction[]>([]);
  const [loading, setLoading] = useState(true);

  function load() {
    setLoading(true);
    fetchNeedsReview().then((r) => { setRows(r); setLoading(false); });
  }
  useEffect(load, []);

  return (
    <>
      <h1 className="page">Por revisar / sin categoría</h1>
      <p className="muted">
        Correos que el parser no pudo leer bien ({"needs_review"}) o transacciones sin
        categoría. Corrígelas y, si quieres, crea una regla para la próxima vez.
      </p>
      <div className="card">
        {loading ? <p className="muted">Cargando…</p> : <TxnTable rows={rows} onChange={load} />}
      </div>
    </>
  );
}
