import { useEffect, useState } from "react";
import { fetchInsights, regenerateInsights } from "../lib/queries";
import { fmtDate } from "../lib/time";
import MiniMarkdown from "../components/MiniMarkdown";
import type { Insight } from "../lib/types";

export default function Insights() {
  const [items, setItems] = useState<Insight[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  function load() { fetchInsights().then(setItems); }
  useEffect(load, []);

  async function regen() {
    setBusy(true); setMsg(null);
    const res = await regenerateInsights();
    setBusy(false);
    if (res.error) setMsg(`Error: ${res.error}`);
    else { setMsg("Recomendaciones actualizadas."); load(); }
  }

  return (
    <>
      <h1 className="page">Recomendaciones para gastar menos</h1>
      <div className="row" style={{ alignItems: "center", marginBottom: 12 }}>
        <button className="primary" onClick={regen} disabled={busy}>
          {busy ? "Generando…" : "Regenerar ahora"}
        </button>
        {msg && <span className="muted">{msg}</span>}
      </div>

      {items.length === 0 && (
        <div className="card"><p className="muted">
          Aún no hay recomendaciones. Pulsa "Regenerar ahora" (se generan también cada
          lunes automáticamente).
        </p></div>
      )}

      {items.map((it) => (
        <div className="card" key={it.id}>
          <h2>Semana del {fmtDate(it.week)} {it.model && <span className="muted">· {it.model}</span>}</h2>
          <MiniMarkdown text={it.content} />
        </div>
      ))}
    </>
  );
}
