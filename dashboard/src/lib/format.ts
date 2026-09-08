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
