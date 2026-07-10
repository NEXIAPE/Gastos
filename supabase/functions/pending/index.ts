// Edge Function: pending
// Devuelve los gastos (out) que quedaron SIN categoría en los últimos días,
// para armar el correo-resumen diario. Protegido con DIGEST_TOKEN.
//
// GET /pending?token=<DIGEST_TOKEN>   (o header Authorization: Bearer <token>)

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";
import { corsHeaders, json } from "../_shared/cors.ts";

const admin = createClient(Deno.env.get("SUPABASE_URL")!, Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!, {
  auth: { persistSession: false },
});
const DIGEST_TOKEN = Deno.env.get("DIGEST_TOKEN")!;

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });

  const url = new URL(req.url);
  const token = url.searchParams.get("token") ??
    (req.headers.get("Authorization") ?? "").replace(/^Bearer\s+/i, "").trim();
  if (!DIGEST_TOKEN || token !== DIGEST_TOKEN) return json({ error: "unauthorized" }, 401);

  const days = Number(url.searchParams.get("days") ?? "12");
  const since = new Date(Date.now() - days * 86400_000).toISOString();

  const [txns, cats] = await Promise.all([
    admin.from("transactions")
      .select("id, merchant_clean, merchant_raw, amount_pen, occurred_at, channel")
      .eq("category", "Sin categoría")
      .eq("direction", "out")
      .neq("status", "declined")
      .gte("occurred_at", since)
      .order("occurred_at", { ascending: false })
      .limit(50),
    admin.from("categories")
      .select("name")
      .neq("name", "Sin categoría")
      .order("expense_group")
      .order("name"),
  ]);

  if (txns.error) return json({ error: "query_failed", detail: txns.error.message }, 500);
  return json({
    pending: txns.data ?? [],
    categories: (cats.data ?? []).map((c: { name: string }) => c.name),
    // Diagnóstico: si categories viene vacío por un error real (no porque la
    // tabla esté vacía), aquí se ve la causa en vez de fallar en silencio.
    categories_error: cats.error ? cats.error.message : undefined,
  });
});
