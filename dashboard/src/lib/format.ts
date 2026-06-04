export function soles(n: number | null | undefined): string {
  const v = Number(n ?? 0);
  return v.toLocaleString("es-PE", {
    style: "currency", currency: "PEN", minimumFractionDigits: 2,
  });
}

export function pct(value: number, base: number): string {
  if (!base) return "—";
  const p = ((value - base) / base) * 100;
  const sign = p >= 0 ? "+" : "";
  return `${sign}${p.toFixed(0)}%`;
}

// Paleta estable para categorías/canales en los gráficos.
const PALETTE = [
  "#2563eb", "#16a34a", "#dc2626", "#d97706", "#7c3aed", "#0891b2",
  "#db2777", "#65a30d", "#ea580c", "#4f46e5", "#0d9488", "#b45309",
  "#9333ea", "#059669", "#e11d48", "#475569", "#ca8a04", "#0ea5e9",
];
export function colorFor(key: string): string {
  let h = 0;
  for (let i = 0; i < key.length; i++) h = (h * 31 + key.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}
