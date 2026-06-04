// Helpers de fecha en zona America/Lima (UTC-5, sin horario de verano).
// Los cortes de día y mes del dashboard se calculan en esta zona.

const LIMA_OFFSET = "-05:00";
const pad = (n: number) => String(n).padStart(2, "0");

/** "Ahora" como hora de pared en Lima (usando el instante actual desplazado). */
function limaNow(): Date {
  return new Date(Date.now() - 5 * 3600_000);
}

/** Año y mes (0-index) actuales en Lima. */
export function currentLimaYearMonth(): { year: number; month: number } {
  const d = limaNow();
  return { year: d.getUTCFullYear(), month: d.getUTCMonth() };
}

/** Rango [start, end) en ISO con offset de Lima para un mes dado. */
export function monthRange(year: number, month: number): { start: string; end: string; label: string } {
  const start = `${year}-${pad(month + 1)}-01T00:00:00${LIMA_OFFSET}`;
  const ny = month === 11 ? year + 1 : year;
  const nm = month === 11 ? 0 : month + 1;
  const end = `${ny}-${pad(nm + 1)}-01T00:00:00${LIMA_OFFSET}`;
  const label = new Date(Date.UTC(year, month, 1)).toLocaleDateString("es-PE", {
    month: "long", year: "numeric", timeZone: "UTC",
  });
  return { start, end, label };
}

/** Lista de los últimos N meses (incluido el actual), del más antiguo al más nuevo. */
export function lastNMonths(n: number): { year: number; month: number; key: string; label: string }[] {
  const { year, month } = currentLimaYearMonth();
  const out: { year: number; month: number; key: string; label: string }[] = [];
  for (let i = n - 1; i >= 0; i--) {
    let y = year, m = month - i;
    while (m < 0) { m += 12; y -= 1; }
    const label = new Date(Date.UTC(y, m, 1)).toLocaleDateString("es-PE", {
      month: "short", year: "2-digit", timeZone: "UTC",
    });
    out.push({ year: y, month: m, key: `${y}-${pad(m + 1)}`, label });
  }
  return out;
}

/** Formatea un timestamptz para mostrar en hora de Lima. */
export function fmtDateTime(iso: string): string {
  return new Date(iso).toLocaleString("es-PE", {
    timeZone: "America/Lima", day: "2-digit", month: "short",
    hour: "2-digit", minute: "2-digit",
  });
}

export function fmtDate(iso: string): string {
  return new Date(iso).toLocaleDateString("es-PE", {
    timeZone: "America/Lima", day: "2-digit", month: "short", year: "numeric",
  });
}

/** Convierte un input datetime-local (hora Lima) a ISO con offset de Lima. */
export function localInputToLimaIso(value: string): string {
  // value: "2026-06-04T14:30"
  return `${value}:00${LIMA_OFFSET}`;
}
