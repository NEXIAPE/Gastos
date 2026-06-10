import type { Transaction } from "./types";
import { type ExpenseGroup, groupOf } from "./types";

export const sumPen = (rows: { amount_pen: number | null }[]): number =>
  Number(rows.reduce((a, r) => a + (r.amount_pen ?? 0), 0).toFixed(2));

export interface Slice { key: string; value: number }

/** Agrupa y suma amount_pen por un campo, ordenado desc. */
export function groupByPen<T extends { amount_pen: number | null }>(
  rows: T[], key: (r: T) => string | null,
): Slice[] {
  const map = new Map<string, number>();
  for (const r of rows) {
    const k = key(r) ?? "—";
    map.set(k, Number(((map.get(k) ?? 0) + (r.amount_pen ?? 0)).toFixed(2)));
  }
  return [...map.entries()].map(([k, v]) => ({ key: k, value: v }))
    .sort((a, b) => b.value - a.value);
}

/** Clave de mes (YYYY-MM) en hora de Lima para un timestamptz. */
export function limaMonthKey(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Lima", year: "numeric", month: "2-digit",
  }).format(new Date(iso)); // "2026-06"
}

export const byCategory = (rows: Transaction[]) => groupByPen(rows, (r) => r.category);
export const byChannel = (rows: Transaction[]) => groupByPen(rows, (r) => r.channel);
export const byMerchant = (rows: Transaction[]) => groupByPen(rows, (r) => r.merchant_clean);
export const byGroup = (rows: Transaction[]) => groupByPen(rows, (r) => groupOf(r.category));

/** Suma del gasto de las categorías que pertenecen a un Tipo de Gasto. */
export const sumByGroup = (rows: Transaction[], group: ExpenseGroup): number =>
  sumPen(rows.filter((r) => groupOf(r.category) === group));

/** Suma del gasto de una categoría puntual (ej. Luna). */
export const sumByCategory = (rows: Transaction[], category: string): number =>
  sumPen(rows.filter((r) => r.category === category));
