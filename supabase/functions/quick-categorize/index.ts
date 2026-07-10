// Edge Function: quick-categorize
// Categoriza una transacción con 1 toque desde el correo-resumen. Devuelve una
// mini página de confirmación. Protegido con DIGEST_TOKEN.
//
// GET /quick-categorize?id=<uuid>&cat=<categoria>&token=<DIGEST_TOKEN>

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
text-align:center;box-shadow:0 2px 12px rgba(40,30,80,.06)">
${body}
${DASHBOARD_URL ? `<p style="margin-top:18px"><a href="${DASHBOARD_URL}" style="color:#6c5ce7;font-size:14px">Abrir dashboard →</a></p>` : ""}
</div></body></html>`;
  return new Response(html, { status, headers: { ...corsHeaders, "Content-Type": "text/html; charset=utf-8" } });
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
  if (!id || !cat) {
    return page("Faltan datos", `<div style="font-size:40px">⚠️</div><h2>Enlace incompleto</h2>`, 400);
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
<p style="font-size:15px"><b>${data.merchant_clean ?? ""}</b> · ${monto}</p>
<p style="display:inline-block;margin-top:8px;background:#efecfd;color:#6c5ce7;
padding:6px 14px;border-radius:999px;font-weight:600">${cat}</p>`);
});
