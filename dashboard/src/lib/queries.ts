import { supabase } from "./supabase";
import type { Budget, CategoryRule, Insight, Transaction } from "./types";

const TXN_COLS =
  "id, occurred_at, merchant_raw, merchant_clean, amount, direction, status, refund_of, " +
  "is_recurring, counterparty, currency, fx_rate, amount_pen, category, card_label, source, " +
  "channel, notes, tags, external_ref, created_at, updated_at";

// ---- Gasto (out + confirmed) ----
export async function fetchSpend(start: string, end: string): Promise<Transaction[]> {
  const { data, error } = await supabase
    .from("transactions").select(TXN_COLS)
    .eq("direction", "out").eq("status", "confirmed")
    .gte("occurred_at", start).lt("occurred_at", end)
    .order("occurred_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as unknown as Transaction[];
}

// ---- Reembolsos/extornos (se restan del gasto neto) ----
export async function fetchRefunds(start: string, end: string): Promise<Transaction[]> {
  const { data, error } = await supabase
    .from("transactions").select(TXN_COLS)
    .in("status", ["refunded", "reversed"])
    .gte("occurred_at", start).lt("occurred_at", end);
  if (error) throw error;
  return (data ?? []) as unknown as Transaction[];
}

// ---- Dinero recibido (in) ----
export async function fetchReceived(start: string, end: string): Promise<Transaction[]> {
  const { data, error } = await supabase
    .from("transactions").select(TXN_COLS)
    .eq("direction", "in")
    .gte("occurred_at", start).lt("occurred_at", end)
    .order("occurred_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as unknown as Transaction[];
}

// ---- Gasto confirmado desde una fecha (para tendencia mensual) ----
export async function fetchSpendSince(startIso: string): Promise<Transaction[]> {
  const { data, error } = await supabase
    .from("transactions").select("occurred_at, amount_pen, category, channel")
    .eq("direction", "out").eq("status", "confirmed")
    .gte("occurred_at", startIso);
  if (error) throw error;
  return (data ?? []) as unknown as Transaction[];
}

// ---- Bandeja por revisar ----
export async function fetchNeedsReview(): Promise<Transaction[]> {
  const { data, error } = await supabase
    .from("transactions").select(TXN_COLS)
    .or("status.eq.needs_review,category.eq.Sin categoría")
    .order("occurred_at", { ascending: false }).limit(500);
  if (error) throw error;
  return (data ?? []) as unknown as Transaction[];
}

// ---- Lista filtrable ----
export interface TxnFilters {
  from?: string; to?: string; category?: string; channel?: string;
  direction?: string; merchant?: string; status?: string;
}
export async function fetchTransactions(f: TxnFilters): Promise<Transaction[]> {
  let q = supabase.from("transactions").select(TXN_COLS)
    .order("occurred_at", { ascending: false }).limit(1000);
  if (f.from) q = q.gte("occurred_at", f.from);
  if (f.to) q = q.lt("occurred_at", f.to);
  if (f.category) q = q.eq("category", f.category);
  if (f.channel) q = q.eq("channel", f.channel);
  if (f.direction) q = q.eq("direction", f.direction);
  if (f.status) q = q.eq("status", f.status);
  if (f.merchant) q = q.ilike("merchant_clean", `%${f.merchant}%`);
  const { data, error } = await q;
  if (error) throw error;
  return (data ?? []) as unknown as Transaction[];
}

export async function updateTransaction(id: string, patch: Partial<Transaction>): Promise<void> {
  const { error } = await supabase.from("transactions").update(patch).eq("id", id);
  if (error) throw error;
}

export async function deleteTransaction(id: string): Promise<void> {
  const { error } = await supabase.from("transactions").delete().eq("id", id);
  if (error) throw error;
}

export async function insertManual(row: Partial<Transaction>): Promise<void> {
  const { error } = await supabase.from("transactions").insert(row);
  if (error) throw error;
}

// ---- Recategorización masiva por comercio ----
export async function bulkRecategorize(merchantLike: string, category: string): Promise<void> {
  const { error } = await supabase.from("transactions")
    .update({ category }).ilike("merchant_clean", `%${merchantLike}%`);
  if (error) throw error;
}

// ---- Reglas ----
export async function fetchRules(): Promise<CategoryRule[]> {
  const { data, error } = await supabase.from("category_rules")
    .select("*").order("priority", { ascending: false });
  if (error) throw error;
  return (data ?? []) as unknown as CategoryRule[];
}
export async function addRule(match_text: string, category: string, priority: number): Promise<void> {
  const { error } = await supabase.from("category_rules")
    .insert({ match_text: match_text.toUpperCase(), category, priority });
  if (error) throw error;
}
export async function deleteRule(id: string): Promise<void> {
  const { error } = await supabase.from("category_rules").delete().eq("id", id);
  if (error) throw error;
}

// ---- Settings (tipo de cambio fijo) ----
export async function getFxRate(): Promise<number> {
  const { data } = await supabase.from("settings").select("value").eq("key", "fx_usd_pen").maybeSingle();
  const n = Number(data?.value);
  return Number.isFinite(n) && n > 0 ? n : 3.75;
}
export async function setFxRate(rate: number): Promise<void> {
  const { error } = await supabase.from("settings")
    .upsert({ key: "fx_usd_pen", value: rate, updated_at: new Date().toISOString() });
  if (error) throw error;
}

// ---- Settings (nombres propios, para detectar transferencias a mí mismo) ----
export async function getSelfNames(): Promise<string[]> {
  const { data } = await supabase.from("settings").select("value").eq("key", "self_names").maybeSingle();
  return Array.isArray(data?.value) ? (data!.value as unknown[]).map((v) => String(v)) : [];
}
export async function setSelfNames(names: string[]): Promise<void> {
  const { error } = await supabase.from("settings")
    .upsert({ key: "self_names", value: names, updated_at: new Date().toISOString() });
  if (error) throw error;
}

// ---- Presupuestos (fase 2) ----
export async function fetchBudgets(): Promise<Budget[]> {
  const { data, error } = await supabase.from("budgets").select("*");
  if (error) throw error;
  return (data ?? []) as unknown as Budget[];
}
export async function upsertBudget(category: string, amount_pen: number): Promise<void> {
  const { error } = await supabase.from("budgets")
    .upsert({ category, amount_pen, period: "monthly", active: true }, { onConflict: "category" });
  if (error) throw error;
}
export async function deleteBudget(category: string): Promise<void> {
  const { error } = await supabase.from("budgets").delete().eq("category", category);
  if (error) throw error;
}

// ---- Insights ----
export async function fetchInsights(): Promise<Insight[]> {
  const { data, error } = await supabase.from("insights")
    .select("*").order("week", { ascending: false }).limit(12);
  if (error) throw error;
  return (data ?? []) as unknown as Insight[];
}
export async function regenerateInsights(): Promise<{ content?: string; error?: string }> {
  const { data, error } = await supabase.functions.invoke("weekly-insights", { body: {} });
  if (error) return { error: error.message };
  return { content: (data as { content?: string })?.content };
}

// ---- Salud: fecha de la última transacción ----
export async function lastTransactionAt(): Promise<string | null> {
  const { data } = await supabase.from("transactions")
    .select("created_at").order("created_at", { ascending: false }).limit(1).maybeSingle();
  return data?.created_at ?? null;
}

// ---- Borrar todo (zona de peligro) ----
export async function deleteAllTransactions(): Promise<void> {
  const { error } = await supabase.from("transactions")
    .delete().neq("id", "00000000-0000-0000-0000-000000000000");
  if (error) throw error;
}
