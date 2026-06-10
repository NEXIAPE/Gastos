import { useEffect, useState } from "react";
import { fetchTransactions, type TxnFilters } from "../lib/queries";
import { CATEGORIES, CHANNELS, CHANNEL_LABEL, DIRECTIONS, STATUSES } from "../lib/types";
import { localInputToLimaIso } from "../lib/time";
import { soles } from "../lib/format";
import { sumPen } from "../lib/aggregate";
import { downloadCsv, toCsv } from "../lib/csv";
import TxnTable from "../components/TxnTable";
import type { Transaction } from "../lib/types";

export default function Transacciones() {
  const [rows, setRows] = useState<Transaction[]>([]);
  const [merchant, setMerchant] = useState("");
  const [category, setCategory] = useState("");
  const [channel, setChannel] = useState("");
  const [direction, setDirection] = useState("");
  const [status, setStatus] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  function load() {
    const f: TxnFilters = {
      merchant: merchant || undefined,
      category: category || undefined,
      channel: channel || undefined,
      direction: direction || undefined,
      status: status || undefined,
      from: from ? localInputToLimaIso(`${from}T00:00`) : undefined,
      to: to ? localInputToLimaIso(`${to}T23:59`) : undefined,
    };
    fetchTransactions(f).then(setRows);
  }
  useEffect(load, []); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <h1 className="page">Transacciones</h1>
      <div className="filters">
        <div className="field"><label>Comercio</label>
          <input value={merchant} onChange={(e) => setMerchant(e.target.value)} placeholder="buscar…" /></div>
        <div className="field"><label>Categoría</label>
          <select value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Todas</option>{CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select></div>
        <div className="field"><label>Canal</label>
          <select value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="">Todos</option>
            {CHANNELS.map((c) => <option key={c} value={c}>{CHANNEL_LABEL[c]}</option>)}
          </select></div>
        <div className="field"><label>Dirección</label>
          <select value={direction} onChange={(e) => setDirection(e.target.value)}>
            <option value="">Todas</option>{DIRECTIONS.map((d) => <option key={d}>{d}</option>)}
          </select></div>
        <div className="field"><label>Estado</label>
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Todos</option>{STATUSES.map((s) => <option key={s}>{s}</option>)}
          </select></div>
        <div className="field"><label>Desde</label>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} /></div>
        <div className="field"><label>Hasta</label>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} /></div>
        <button className="primary" onClick={load}>Filtrar</button>
        <button onClick={() => downloadCsv("gastos.csv", toCsv(rows))}>Exportar CSV</button>
      </div>

      <p className="muted">
        {rows.length} resultados · gasto (out/confirmed):{" "}
        {soles(sumPen(rows.filter((r) => r.direction === "out" && r.status === "confirmed")))}
      </p>
      <div className="card"><TxnTable rows={rows} onChange={load} /></div>
    </>
  );
}
