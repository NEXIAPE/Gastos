import { useEffect, useState } from "react";
import { GROUP_COLOR_DARK, GROUP_COLOR_LIGHT, type ExpenseGroup } from "./types";

/** true si el sistema está en modo oscuro (el dashboard no tiene toggle manual). */
export function useDarkMode(): boolean {
  const query = "(prefers-color-scheme: dark)";
  const [dark, setDark] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const mq = window.matchMedia(query);
    const onChange = (e: MediaQueryListEvent) => setDark(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return dark;
}

/** Color validado (CVD-safe) para un Tipo de Gasto, según el modo actual. */
export function groupColor(group: ExpenseGroup, dark: boolean): string {
  return (dark ? GROUP_COLOR_DARK : GROUP_COLOR_LIGHT)[group] ?? (dark ? "#c3c2b7" : "#898781");
}
