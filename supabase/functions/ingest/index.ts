// Edge Function: POST /ingest
// Recibe eventos del Atajo de Apple Pay y del Apps Script de Gmail.
// Valida token, normaliza, categoriza, deduplica (idempotente) e inserta.
//
// Secrets requeridos:
//   INGEST_TOKEN               token dedicado para el header Authorization
//   SUPABASE_URL               (inyectado por Supabase)
//   SUPABASE_SERVICE_ROLE_KEY  (inyectado por Supabase)

import { createClient } from "https://esm.sh/@supabase/supabase-js@2.45.4";
import { corsHeaders, json } from "../_shared/cors.ts";
import {
  categorize,
  cleanMerchant,
  type CategoryRule,
  detectDirection,
  detectStatus,
  type Direction,
  looksRecurring,
  type Status,
} from "../_shared/normalize.ts";

const SUPABASE_URL = Deno.env.get("SUPABASE_URL")!;
const SERVICE_ROLE = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!;
const INGEST_TOKEN = Deno.env.get("INGEST_TOKEN")!;

const admin = createClient(SUPABASE_URL, SERVICE_ROLE, {
  auth: { persistSession: false },
});

const DEDUP_WINDOW_MIN = 60; // ventana cross-source
const RETRY_WINDOW_SEC = 90; // guarda anti-reintento mismo origen

interface IngestBody {
  source: string;
  channel?: string;
  direction?: Direction;
  status?: Status;
  occurred_at?: string;
  merchant?: string;
  amount?: number | string;
  currency?: string;
  category?: string; // categoría explícita (ej. atajo manual con selector)
  card_label?: string;
  counterparty?: string;
  external_ref?: string;
  amount_pen?: number | string; // si el correo ya trae el monto en soles
  notes?: string;
  text?: string; // texto crudo del correo, para inferir dirección/estado
  raw_payload?: unknown;
}

async function getFxRate(): Promise<number> {
  const { data } = await admin.from("settings").select("value").eq("key", "fx_usd_pen").maybeSingle();
  const v = data?.value;
  const n = typeof v === "number" ? v : parseFloat(String(v));
  return Number.isFinite(n) && n > 0 ? n : 3.75;
}

// Nombres/alias propios del usuario. Si la contraparte coincide, el movimiento
// es una transferencia a sí mismo (no es gasto). 100% configurable desde el
// dashboard (Ajustes → "Mis nombres"), sin nada hardcodeado ni redeploy.
async function getSelfNames(): Promise<string[]> {
  const { data } = await admin.from("settings").select("value").eq("key", "self_names").maybeSingle();
  const names = Array.isArray(data?.value) ? (data!.value as unknown[]).map((x) => String(x)) : [];
  return [...new Set(names.map((s) => s.toUpperCase().trim()))].filter(Boolean);
}

async function getRules(): Promise<CategoryRule[]> {
  const { data } = await admin.from("category_rules").select("match_text, category, priority");
  return (data ?? []) as CategoryRule[];
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  // --- Auth ---
  const auth = req.headers.get("Authorization") ?? "";
  const token = auth.replace(/^Bearer\s+/i, "").trim();
  if (!INGEST_TOKEN || token !== INGEST_TOKEN) {
    return json({ error: "unauthorized" }, 401);
  }

  let body: IngestBody;
  try {
    body = await req.json();
  } catch {
    return json({ error: "invalid_json" }, 400);
  }

  // --- Validación mínima ---
  const amount = typeof body.amount === "string" ? parseFloat(body.amount) : body.amount;
  if (!body.merchant || amount === undefined || amount === null || !Number.isFinite(amount)) {
    return json({ error: "missing_fields", detail: "merchant y amount son obligatorios" }, 400);
  }

  // --- Normalización ---
  const currency = (body.currency ?? "PEN").toUpperCase() === "USD" ? "USD" : "PEN";
  const merchant_raw = body.merchant;
  const merchant_clean = cleanMerchant(merchant_raw);
  const inferText = [body.text, body.notes, merchant_raw].filter(Boolean).join(" ");

  // Dirección: la explícita manda; si no, se infiere; si no, needs_review.
  let direction: Direction = body.direction ?? detectDirection(inferText) ?? "out";
  const directionWasUncertain = !body.direction && detectDirection(inferText) === null;

  // Estado: el explícito manda; si no, se infiere del texto.
  let status: Status = body.status ?? detectStatus(inferText);
  if (directionWasUncertain && status === "confirmed") status = "needs_review";

  // Transferencia a sí mismo: si la contraparte/comercio es el propio usuario
  // (ej. yapearse a tu propio Plin), NO es gasto → direction 'transfer'.
  const whoText = `${body.counterparty ?? ""} ${merchant_clean}`.toUpperCase();
  const selfNames = await getSelfNames();
  if (selfNames.some((n) => whoText.includes(n))) {
    direction = "transfer";
    if (status === "needs_review") status = "confirmed"; // ya sabemos qué es
  }

  // Monto en soles (tipo de cambio fijo configurable).
  let fx_rate: number | null = null;
  let amount_pen: number;
  const providedPen = body.amount_pen !== undefined ? Number(body.amount_pen) : NaN;
  if (currency === "USD") {
    if (Number.isFinite(providedPen) && providedPen > 0) {
      amount_pen = Number(providedPen.toFixed(2));
      fx_rate = Number((amount_pen / amount).toFixed(4));
    } else {
      fx_rate = await getFxRate();
      amount_pen = Number((amount * fx_rate).toFixed(2));
    }
  } else {
    amount_pen = Number(amount.toFixed(2));
  }

  // Categoría: si el evento trae una explícita (ej. atajo manual con selector),
  // se respeta; si no, se asigna por reglas de comercio.
  const rules = await getRules();
  const category = (body.category && body.category.trim())
    ? body.category.trim()
    : categorize(merchant_clean, rules);
  const occurred_at = body.occurred_at ?? new Date().toISOString();

  const row = {
    occurred_at,
    merchant_raw,
    merchant_clean,
    amount: Number(amount.toFixed(2)),
    direction,
    status,
    counterparty: body.counterparty ?? null,
    currency,
    fx_rate,
    amount_pen,
    category,
    card_label: body.card_label ?? null,
    source: body.source ?? "manual",
    channel: body.channel ?? null,
    notes: body.notes ?? null,
    is_recurring: looksRecurring(merchant_clean),
    external_ref: body.external_ref ?? null,
    raw_payload: body.raw_payload ?? body as unknown,
  };

  // --- Deduplicación ---

  // 1) Idempotencia por external_ref: si ya existe ese ref, no hacemos nada.
  if (row.external_ref) {
    const { data: existing } = await admin
      .from("transactions").select("id").eq("external_ref", row.external_ref).maybeSingle();
    if (existing) return json({ status: "ok", deduped: true, id: existing.id });
  }

  // 2) Ventana de tiempo: corre SIEMPRE (con o sin external_ref) para poder
  //    fusionar la misma compra que llega por dos fuentes distintas, p.ej. el
  //    Atajo de Apple Pay (sin ref) llega primero y el correo del banco
  //    (con voucher) después.
  const t = new Date(occurred_at).getTime();
  const fromWindow = new Date(t - DEDUP_WINDOW_MIN * 60_000).toISOString();
  const toWindow = new Date(t + DEDUP_WINDOW_MIN * 60_000).toISOString();

  const { data: candidates } = await admin
    .from("transactions")
    .select("id, source, occurred_at, card_label, counterparty, channel, external_ref")
    .eq("amount", row.amount)
    .eq("currency", row.currency)
    .eq("merchant_clean", row.merchant_clean)
    .gte("occurred_at", fromWindow)
    .lte("occurred_at", toWindow);

  if (candidates && candidates.length > 0) {
    // 2a) Reintento del mismo origen (±90s) → idempotente, no insertar.
    const retry = candidates.find(
      (c) => c.source === row.source &&
        Math.abs(new Date(c.occurred_at).getTime() - t) <= RETRY_WINDOW_SEC * 1000,
    );
    if (retry) return json({ status: "ok", deduped: true, id: retry.id });

    // 2b) Misma compra por fuente distinta (Apple Pay vs correo del banco) → fusionar.
    const other = candidates.find((c) => c.source !== row.source);
    if (other) {
      const patch: Record<string, unknown> = {};
      if (!other.card_label && row.card_label) patch.card_label = row.card_label;
      if (!other.counterparty && row.counterparty) patch.counterparty = row.counterparty;
      if (!other.channel && row.channel) patch.channel = row.channel;
      // Si la fila existente no tenía external_ref y este evento sí, lo fijamos:
      // así futuros reenvíos del mismo correo son idempotentes.
      if (!other.external_ref && row.external_ref) patch.external_ref = row.external_ref;
      // El correo del banco es la "fuente de verdad" del monto/estado; si esta
      // fuente es un email_*, dejamos que prevalezca su estado.
      if (row.source.startsWith("email_")) patch.status = row.status;
      if (Object.keys(patch).length) await admin.from("transactions").update(patch).eq("id", other.id);
      return json({ status: "ok", deduped: true, id: other.id });
    }
  }

  // 3) Insertar nuevo (idempotente ante carrera por external_ref).
  const { data, error } = await admin.from("transactions").insert(row).select("id").single();
  if (error) {
    if (row.external_ref) {
      const { data: again } = await admin
        .from("transactions").select("id").eq("external_ref", row.external_ref).maybeSingle();
      if (again) return json({ status: "ok", deduped: true, id: again.id });
    }
    return json({ error: "insert_failed", detail: error.message }, 500);
  }
  return json({ status: "ok", deduped: false, id: data.id });
});
