import { useEffect, useState } from "react";
import { supabase } from "./supabase";
import type { ExpenseGroup } from "./types";

export interface CategoryDef {
  name: string;
  expense_group: ExpenseGroup;
}

// Respaldo mientras carga la primera vez (o si falla la red).
const FALLBACK: CategoryDef[] = [
  { name: "Vivienda/Casa", expense_group: "Fijo" },
  { name: "Servicios", expense_group: "Fijo" },
  { name: "Sin categoría", expense_group: "Otros" },
];

let cache: CategoryDef[] = FALLBACK;
let groupMap: Record<string, ExpenseGroup> = Object.fromEntries(FALLBACK.map((c) => [c.name, c.expense_group]));
let inflight: Promise<CategoryDef[]> | null = null;
const listeners = new Set<(cats: CategoryDef[]) => void>();

function setCache(cats: CategoryDef[]) {
  cache = cats;
  groupMap = Object.fromEntries(cats.map((c) => [c.name, c.expense_group]));
  listeners.forEach((fn) => fn(cache));
}

async function loadCategories(): Promise<CategoryDef[]> {
  const { data, error } = await supabase
    .from("categories").select("name, expense_group").order("expense_group").order("name");
  inflight = null;
  if (error || !data || data.length === 0) return cache;
  setCache(data as unknown as CategoryDef[]);
  return cache;
}

export function fetchCategories(force = false): Promise<CategoryDef[]> {
  if (inflight && !force) return inflight;
  inflight = loadCategories();
  return inflight;
}

/** Tipo de Gasto de una categoría (síncrono, usa la caché en memoria). */
export const groupOf = (cat: string): ExpenseGroup => groupMap[cat] ?? "Otros";

export async function addCategory(name: string, group: ExpenseGroup): Promise<void> {
  const clean = name.trim();
  if (!clean) return;
  const { error } = await supabase.from("categories").upsert({ name: clean, expense_group: group });
  if (error) throw error;
  await fetchCategories(true);
}

export async function deleteCategory(name: string): Promise<void> {
  const { error } = await supabase.from("categories").delete().eq("name", name);
  if (error) throw error;
  await fetchCategories(true);
}

/** Lista reactiva de categorías; se carga una vez y se comparte entre componentes. */
export function useCategories() {
  const [categories, setCategories] = useState<CategoryDef[]>(cache);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const listener = (cats: CategoryDef[]) => setCategories(cats);
    listeners.add(listener);
    fetchCategories().then((cats) => { setCategories(cats); setLoading(false); });
    return () => { listeners.delete(listener); };
  }, []);

  return { categories, names: categories.map((c) => c.name), loading, reload: () => fetchCategories(true) };
}
