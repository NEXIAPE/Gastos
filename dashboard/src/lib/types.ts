export type Direction = "out" | "in" | "transfer";
export type Status =
  | "confirmed" | "declined" | "reversed" | "refunded" | "pending" | "needs_review";
export type Channel = "apple_pay" | "yape" | "plin" | "tarjeta" | "efectivo";

export interface Transaction {
  id: string;
  occurred_at: string;
  merchant_raw: string | null;
  merchant_clean: string | null;
  amount: number;
  direction: Direction;
  status: Status;
  refund_of: string | null;
  is_recurring: boolean;
  counterparty: string | null;
  currency: "PEN" | "USD";
  fx_rate: number | null;
  amount_pen: number | null;
  category: string;
  card_label: string | null;
  source: string;
  channel: Channel | null;
  notes: string | null;
  tags: string[];
  external_ref: string | null;
  raw_payload: unknown;
  created_at: string;
  updated_at: string;
}

export interface CategoryRule {
  id: string;
  match_text: string;
  category: string;
  priority: number;
  created_at: string;
}

export interface Insight {
  id: string;
  week: string;
  content: string;
  summary: unknown;
  model: string | null;
  created_at: string;
}

// Las categorías en sí ahora son dinámicas (tabla `categories`, agregables
// desde Ajustes) — ver lib/categories.ts. Los "Tipo de Gasto" son fijos.
export const EXPENSE_GROUPS = [
  "Fijo", "Necesario", "Bienestar", "Lifestyle", "Compras", "Inversión", "Otros",
] as const;
export type ExpenseGroup = (typeof EXPENSE_GROUPS)[number];

// Paleta categórica validada (skill dataviz): 7 tonos fijos, en orden fijo,
// verificados con validate_palette.js contra los fondos reales de la app
// (light #ffffff / dark #1e1e28) — todos los checks pasan en ambos modos.
// Cada Tipo de Gasto tiene su propio par claro/oscuro (no un flip automático).
export const GROUP_COLOR_LIGHT: Record<ExpenseGroup, string> = {
  Fijo: "#2a78d6", Necesario: "#eb6834", Bienestar: "#1baf7a", Lifestyle: "#eda100",
  Compras: "#e87ba4", "Inversión": "#008300", Otros: "#e34948",
};
export const GROUP_COLOR_DARK: Record<ExpenseGroup, string> = {
  Fijo: "#3987e5", Necesario: "#d95926", Bienestar: "#199e70", Lifestyle: "#c98500",
  Compras: "#d55181", "Inversión": "#008300", Otros: "#e66767",
};

export interface Budget {
  id: string;
  category: string;
  amount_pen: number;
  period: string;
  active: boolean;
  created_at: string;
}

export const CHANNELS: Channel[] = ["apple_pay", "yape", "plin", "tarjeta", "efectivo"];
export const DIRECTIONS: Direction[] = ["out", "in", "transfer"];
export const STATUSES: Status[] =
  ["confirmed", "declined", "reversed", "refunded", "pending", "needs_review"];

export const CHANNEL_LABEL: Record<string, string> = {
  apple_pay: "Apple Pay", yape: "Yape", plin: "Plin", tarjeta: "Tarjeta", efectivo: "Efectivo",
};
