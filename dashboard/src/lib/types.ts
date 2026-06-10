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

export const CATEGORIES = [
  // Fijo
  "Vivienda/Casa", "Servicios", "Impuestos", "Suscripciones",
  // Necesario
  "Mercado/minimarket", "Transporte", "Combustible", "Luna", "Salud",
  // Bienestar
  "Deporte",
  // Lifestyle
  "Comer fuera", "Delivery", "Antojos", "Salidas", "Entretenimiento", "Viajes",
  // Compras
  "Compras personales", "Hogar",
  // Inversión
  "Educación y Desarrollo",
  // Otros
  "Otros", "Sin categoría",
];

// Agrupación de categorías en "Tipo de Gasto".
export const EXPENSE_GROUPS = [
  "Fijo", "Necesario", "Bienestar", "Lifestyle", "Compras", "Inversión", "Otros",
] as const;
export type ExpenseGroup = (typeof EXPENSE_GROUPS)[number];

export const CATEGORY_GROUP: Record<string, ExpenseGroup> = {
  "Vivienda/Casa": "Fijo", "Servicios": "Fijo", "Impuestos": "Fijo", "Suscripciones": "Fijo",
  "Mercado/minimarket": "Necesario", "Transporte": "Necesario", "Combustible": "Necesario",
  "Luna": "Necesario", "Salud": "Necesario",
  "Deporte": "Bienestar",
  "Comer fuera": "Lifestyle", "Delivery": "Lifestyle", "Antojos": "Lifestyle",
  "Salidas": "Lifestyle", "Entretenimiento": "Lifestyle", "Viajes": "Lifestyle",
  "Compras personales": "Compras", "Hogar": "Compras",
  "Educación y Desarrollo": "Inversión",
  "Otros": "Otros", "Sin categoría": "Otros",
  // Alias heredados (datos antiguos)
  "Compras/tiendas": "Compras",
};

export const GROUP_COLOR: Record<ExpenseGroup, string> = {
  Fijo: "#475569", Necesario: "#2563eb", Bienestar: "#0d9488",
  Lifestyle: "#db2777", Compras: "#d97706", "Inversión": "#16a34a", Otros: "#9ca3af",
};

export const groupOf = (cat: string): ExpenseGroup => CATEGORY_GROUP[cat] ?? "Otros";

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
