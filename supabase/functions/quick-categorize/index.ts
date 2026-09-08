// Edge Function: quick-categorize
// Categoriza una transacción desde el correo-resumen. Protegido con DIGEST_TOKEN.
//
// GET /quick-categorize?id=<uuid>&token=<DIGEST_TOKEN>
//   → sin `cat`: muestra una página con un selector de categoría (1 link por
//     correo en vez de un botón por categoría — así el correo nunca se pasa
//     del límite de tamaño de Gmail, sin importar cuántas categorías tengas).
//   → con `cat`: aplica la categoría y muestra la confirmación.

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";
import { corsHeaders } from "../_shared/cors.ts";

const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
  auth: { persistSession: false },
});
const DIGEST_TOKEN = Deno.env.get("DIGEST_TOKEN")!;
const DASHBOARD_URL = Deno.env.get("DASHBOARD_URL") ?? "";

function page(title: string, body: string, status = 200): Response {
  const html = `<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title></head>
<body style="margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
background:#f5f5fb;color:#2b2b3a;display:flex;min-height:100vh;align-items:center;justify-content:center;padding:20px">
<div style="background:#fff;border:1px solid #ececf3;border-radius:18px;padding:28px;max-width:360px;
width:100%;text-align:center;box-shadow:0 2px 12px rgba(40,30,80,.06)">
${body}
${DASHBOARD_URL ? `<p style="margin-top:18px"><a href="${DASHBOARD_URL}" style="color:#6c5ce7;font-size:14px">Abrir dashboard →</a></p>` : ""}
</div></body></html>`;
  return new Response(html, { status, headers: { ...corsHeaders, "Content-Type": "text/html; charset=utf-8" } });
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  const url = new URL(req.url);
  const token = url.searchParams.get("token") ?? "";
  const id = url.searchParams.get("id") ?? "";
  const cat = (url.searchParams.get("cat") ?? "").trim();

  if (!DIGEST_TOKEN || token !== DIGEST_TOKEN) {
    return page("No autorizado", `<div style="font-size:40px">🔒</div><h2>No autorizado</h2>
<p style="color:#8b8b9e">El enlace no es válido.</p>`, 401);
  }
  if (!id) {
    return page("Faltan datos", `<div style="font-size:40px">⚠️</div><h2>Enlace incompleto</h2>`, 400);
  }

  // Sin categoría en la URL: muestra el selector (formulario GET, sin JS).
  if (!cat) {
    const { data: txn } = await admin
      .from("transactions").select("merchant_clean, merchant_raw, amount_pen").eq("id", id).maybeSingle();
    if (!txn) return page("No encontrado", `<div style="font-size:40px">😕</div><h2>Transacción no encontrada</h2>`, 404);

    const { data: cats } = await admin.from("categories").select("name")
      .neq("name", "Sin categoría").order("expense_group").order("name");
    const options = (cats ?? []).map((c: { name: string }) =>
      `<option value="${escapeHtml(c.name)}">${escapeHtml(c.name)}</option>`).join("");

    const monto = Number(txn.amount_pen ?? 0).toLocaleString("es-PE", { style: "currency", currency: "PEN" });
    const name = txn.merchant_clean || txn.merchant_raw || "(sin nombre)";
    return page("Categorizar", `<div style="font-size:40px">🏷️</div>
<h2 style="margin:10px 0">${escapeHtml(name)} · ${monto}</h2>
<form method="get" action="${url.origin}${url.pathname}">
  <input type="hidden" name="id" value="${escapeHtml(id)}">
  <input type="hidden" name="token" value="${escapeHtml(token)}">
  <select name="cat" required style="width:100%;padding:10px;border-radius:10px;border:1px solid #ececf3;
    font-size:15px;margin-bottom:12px">
    <option value="" disabled selected>Elige una categoría…</option>
    ${options}
  </select>
  <button type="submit" style="width:100%;padding:10px;border-radius:10px;border:none;
    background:#6c5ce7;color:#fff;font-weight:600;font-size:15px">Guardar</button>
</form>`);
  }

  const { data, error } = await admin
    .from("transactions").update({ category: cat }).eq("id", id)
    .select("merchant_clean, amount_pen").maybeSingle();

  if (error || !data) {
    return page("Error", `<div style="font-size:40px">😕</div><h2>No se pudo guardar</h2>
<p style="color:#8b8b9e">${error?.message ?? "Transacción no encontrada"}</p>`, 500);
  }

  const monto = Number(data.amount_pen ?? 0).toLocaleString("es-PE", { style: "currency", currency: "PEN" });
  return page("Listo", `<div style="font-size:40px">✅</div>
<h2 style="margin:10px 0">¡Categorizado!</h2>
<p style="font-size:15px"><b>${escapeHtml(data.merchant_clean ?? "")}</b> · ${monto}</p>
<p style="display:inline-block;margin-top:8px;background:#efecfd;color:#6c5ce7;
padding:6px 14px;border-radius:999px;font-weight:600">${escapeHtml(cat)}</p>`);
});
