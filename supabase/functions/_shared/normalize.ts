// Lógica compartida de normalización, detección de dirección/estado y
// categorización. Sin dependencias de red para poder testearla aislada.

export type Direction = "out" | "in" | "transfer";
export type Status =
  | "confirmed"
  | "declined"
  | "reversed"
  | "refunded"
  | "pending"
  | "needs_review";

export interface CategoryRule {
  match_text: string;
  category: string;
  priority: number;
}

/**
 * Limpia el nombre del comercio: mayúsculas, sin acentos sobrantes, sin códigos
 * basura típicos de los correos bancarios (asteriscos, números de tienda,
 * sufijos de país/ciudad colgantes).
 */
export function cleanMerchant(raw: string | null | undefined): string {
  if (!raw) return "";
  let m = String(raw).toUpperCase().trim();
  // Quitar segmentos tras asterisco/almohadilla (ej. "UBER* TRIP HELP.UBER.COM")
  m = m.replace(/[*#]+/g, " ");
  // Colapsar espacios
  m = m.replace(/\s+/g, " ").trim();
  // Quitar sufijos colgantes comunes (códigos de país / "PE", "LIMA PE", etc.)
  m = m.replace(/\b(PE|PER|PERU|LIMA|SURCO|MIRAFLORES)\b\s*$/g, "").trim();
  // Quitar números/códigos largos colgantes al final (ej. "TOTTUS 0123")
  m = m.replace(/\s+\d{3,}\s*$/g, "").trim();
  return m;
}

const OUT_WORDS = [
  "pagaste", "enviaste", "yapeaste", "tu pago", "compra", "consumo",
  "pago a", "pago de", "cargo", "retiro", "debito", "débito",
];
const IN_WORDS = [
  "recibiste", "te yapearon", "te plinearon", "te enviaron", "abono",
  "ingreso a tu cuenta", "deposito", "depósito", "te depositaron",
];
const TRANSFER_WORDS = [
  "recarga", "recargaste", "transferencia entre", "transferencia a tu",
  "entre tus cuentas", "entre cuentas propias",
];

/**
 * Detecta la dirección del movimiento por las palabras del texto.
 * Devuelve null si no se puede determinar con seguridad (→ needs_review).
 */
export function detectDirection(text: string | null | undefined): Direction | null {
  if (!text) return null;
  const t = text.toLowerCase();
  if (TRANSFER_WORDS.some((w) => t.includes(w))) return "transfer";
  const isOut = OUT_WORDS.some((w) => t.includes(w));
  const isIn = IN_WORDS.some((w) => t.includes(w));
  if (isOut && !isIn) return "out";
  if (isIn && !isOut) return "in";
  return null; // ambiguo
}

const DECLINED_WORDS = ["rechazada", "rechazado", "denegada", "denegado", "no procesada"];
const REVERSED_WORDS = ["extorno", "anulacion", "anulación", "anulada", "reverso", "reversada"];
const REFUNDED_WORDS = ["reembolso", "devolucion", "devolución", "reembolsado"];

export function detectStatus(text: string | null | undefined): Status {
  if (!text) return "confirmed";
  const t = text.toLowerCase();
  if (DECLINED_WORDS.some((w) => t.includes(w))) return "declined";
  if (REVERSED_WORDS.some((w) => t.includes(w))) return "reversed";
  if (REFUNDED_WORDS.some((w) => t.includes(w))) return "refunded";
  return "confirmed";
}

/**
 * Encuentra la categoría según las reglas: el match_text que aparezca en el
 * merchant limpio (case-insensitive), de mayor a menor priority.
 */
export function categorize(merchantClean: string, rules: CategoryRule[]): string {
  const m = (merchantClean || "").toUpperCase();
  let best: CategoryRule | null = null;
  for (const r of rules) {
    if (!r.match_text) continue;
    if (m.includes(r.match_text.toUpperCase())) {
      if (!best || r.priority > best.priority) best = r;
    }
  }
  return best ? best.category : "Sin categoría";
}

const RECURRING_HINTS = [
  "NETFLIX", "SPOTIFY", "DISNEY", "HBO", "YOUTUBE", "APPLE.COM", "GOOGLE",
  "AMAZON PRIME", "ICLOUD", "GYM", "SMARTFIT", "SMART FIT",
];
export function looksRecurring(merchantClean: string): boolean {
  const m = (merchantClean || "").toUpperCase();
  return RECURRING_HINTS.some((h) => m.includes(h));
}
