// Edge Function: weekly-insights
// Arma un resumen de la data real y pide a la API de Claude recomendaciones
// accionables para gastar menos. Guarda el resultado en la tabla `insights`.
//
// Invocación:
//   - Programada (semanal) vía pg_cron usando el service_role key como Bearer.
//   - Bajo demanda desde el dashboard (botón "Regenerar"): pasa el JWT del
//     usuario logueado; verify_jwt=true lo valida.
// Body opcional: { "week": "YYYY-MM-DD" } para regenerar una semana concreta.
//
// Secrets requeridos:
//   ANTHROPIC_API_KEY          API key de Claude
//   INSIGHTS_MODEL             (opcional) default claude-sonnet-4-6
//   SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY (inyectados)

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";
import { corsHeaders, json } from "../_shared/cors.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const ANTHROPIC_API_KEY = Deno.env.get("ANTHROPIC_API_KEY")!;
const MODEL = Deno.env.get("INSIGHTS_MODEL") ?? "claude-sonnet-4-6";

const admin = createClient(SUPABASE_URL, SERVICE_ROLE, { auth: { persistSession: false } });

const pad = (n: number) => String(n).padStart(2, "0");
const LIMA_OFFSET = "-05:00";

/** Devuelve el lunes (inicio de semana) en America/Lima para una fecha dada. */
function limaWeekStart(ref: Date): string {
  const lima = new Date(ref.getTime() - 5 * 3600_000); // Lima = UTC-5, sin DST
  const dow = lima.getUTCDay(); // 0=Dom
  const mondayOffset = (dow + 6) % 7;
  const start = new Date(Date.UTC(lima.getUTCFullYear(), lima.getUTCMonth(), lima.getUTCDate() - mondayOffset));
  return `${start.getUTCFullYear()}-${pad(start.getUTCMonth() + 1)}-${pad(start.getUTCDate())}`;
}

function addDays(dateStr: string, days: number): string {
  const [y, m, d] = dateStr.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + days));
  return `${dt.getUTCFullYear()}-${pad(dt.getUTCMonth() + 1)}-${pad(dt.getUTCDate())}`;
}

const startInstant = (dateStr: string) => `${dateStr}T00:00:00${LIMA_OFFSET}`;

interface Txn {
  occurred_at: string;
  amount_pen: number;
  category: string;
  channel: string | null;
  merchant_clean: string | null;
  is_recurring: boolean;
}

function sum(rows: Txn[]): number {
  return Number(rows.reduce((a, r) => a + (r.amount_pen ?? 0), 0).toFixed(2));
}

function groupSum(rows: Txn[], key: keyof Txn): Record<string, number> {
  const out: Record<string, number> = {};
  for (const r of rows) {
    const k = String(r[key] ?? "—");
    out[k] = Number(((out[k] ?? 0) + (r.amount_pen ?? 0)).toFixed(2));
  }
  return Object.fromEntries(Object.entries(out).sort((a, b) => b[1] - a[1]));
}

async function buildSummary(weekStart: string) {
  const weekEnd = addDays(weekStart, 7);
  const histStart = addDays(weekStart, -7 * 8); // 8 semanas atrás

  // Solo gasto real: out + confirmed.
  const { data } = await admin
    .from("transactions")
    .select("occurred_at, amount_pen, category, channel, merchant_clean, is_recurring")
    .eq("direction", "out")
    .eq("status", "confirmed")
    .gte("occurred_at", startInstant(histStart))
    .lt("occurred_at", startInstant(weekEnd));

  const all = (data ?? []) as Txn[];
  const inWeek = (s: string, e: string) =>
    all.filter((r) => r.occurred_at >= startInstant(s) && r.occurred_at < startInstant(e));

  const thisWeek = inWeek(weekStart, weekEnd);

  // Totales de las 8 semanas previas (para promedio y comparación).
  const prevTotals: number[] = [];
  for (let i = 1; i <= 8; i++) {
    const s = addDays(weekStart, -7 * i);
    prevTotals.push(sum(inWeek(s, addDays(s, 7))));
  }
  const weeksWithData = prevTotals.filter((t) => t > 0);
  const avgPrev = weeksWithData.length
    ? Number((weeksWithData.reduce((a, b) => a + b, 0) / weeksWithData.length).toFixed(2))
    : 0;

  const byCategory = groupSum(thisWeek, "category");
  const byChannel = groupSum(thisWeek, "channel");
  const byMerchant = groupSum(thisWeek, "merchant_clean");
  const topMerchants = Object.fromEntries(Object.entries(byMerchant).slice(0, 8));

  const subs = [...new Set(thisWeek.filter((r) => r.is_recurring).map((r) => r.merchant_clean))]
    .filter(Boolean);

  return {
    week_start: weekStart,
    week_total: sum(thisWeek),
    avg_prev_8w: avgPrev,
    prev_week_total: prevTotals[0] ?? 0,
    by_category: byCategory,
    by_channel: byChannel,
    top_merchants: topMerchants,
    recurring_merchants: subs,
    transaction_count: thisWeek.length,
  };
}

async function callClaude(summary: unknown): Promise<string> {
  const prompt =
    `Eres un asistente financiero personal. A partir del siguiente resumen REAL de ` +
    `gastos semanales (en Soles peruanos S/), genera 3-5 recomendaciones concretas, ` +
    `accionables y específicas para gastar menos.\n\n` +
    `Reglas para tus consejos:\n` +
    `- Usa números y porcentajes reales del resumen (ej. "Gastaste S/240 en delivery, 38% más que tu promedio").\n` +
    `- Prioriza las categorías donde más creció el gasto o más se concentra.\n` +
    `- Detecta posibles suscripciones que no se usan y gastos hormiga repetitivos.\n` +
    `- Tono útil y motivador, sin culpabilizar. Son sugerencias informativas, no asesoría profesional.\n` +
    `- Responde en español, en formato markdown con viñetas. Sé breve y directo.\n\n` +
    `Resumen (JSON):\n${JSON.stringify(summary, null, 2)}`;

  const resp = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json",
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 1024,
      messages: [{ role: "user", content: prompt }],
    }),
  });

  if (!resp.ok) {
    const detail = await resp.text();
    throw new Error(`anthropic_error ${resp.status}: ${detail}`);
  }
  const data = await resp.json();
  return (data.content ?? []).map((c: { text?: string }) => c.text ?? "").join("\n").trim();
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);
  if (!ANTHROPIC_API_KEY) return json({ error: "missing_api_key" }, 500);

  let weekParam: string | undefined;
  try {
    const body = await req.json().catch(() => ({}));
    weekParam = body?.week;
  } catch { /* sin body */ }

  const weekStart = weekParam ?? limaWeekStart(new Date());

  try {
    const summary = await buildSummary(weekStart);
    if (summary.transaction_count === 0) {
      return json({ status: "ok", skipped: true, reason: "no_transactions", week: weekStart });
    }
    const content = await callClaude(summary);

    // Upsert: una recomendación por semana.
    const { data: existing } = await admin
      .from("insights").select("id").eq("week", weekStart).maybeSingle();

    if (existing) {
      await admin.from("insights")
        .update({ content, summary, model: MODEL, created_at: new Date().toISOString() })
        .eq("id", existing.id);
    } else {
      await admin.from("insights").insert({ week: weekStart, content, summary, model: MODEL });
    }

    return json({ status: "ok", week: weekStart, content });
  } catch (e) {
    return json({ error: "insights_failed", detail: String(e) }, 500);
  }
});
