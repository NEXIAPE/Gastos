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
  "Vivienda/Casa", "Impuestos", "Luna", "Comer fuera", "Antojos", "Delivery",
  "Transporte", "Combustible", "Mercado/minimarket", "Compras/tiendas", "Deporte",
  "Servicios", "Entretenimiento", "Suscripciones", "Salud", "Otros", "Sin categoría",
];

export const CHANNELS: Channel[] = ["apple_pay", "yape", "plin", "tarjeta", "efectivo"];
export const DIRECTIONS: Direction[] = ["out", "in", "transfer"];
export const STATUSES: Status[] =
  ["confirmed", "declined", "reversed", "refunded", "pending", "needs_review"];

export const CHANNEL_LABEL: Record<string, string> = {
  apple_pay: "Apple Pay", yape: "Yape", plin: "Plin", tarjeta: "Tarjeta", efectivo: "Efectivo",
};
