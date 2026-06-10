import { useEffect, useState } from "react";
import { lastTransactionAt } from "../lib/queries";

// Aviso de salud: si no entra ninguna transacción en 3+ días, algo se rompió
// (el Atajo o el reenvío de correo). El Atajo es el componente menos confiable.
export default function HealthBanner() {
  const [days, setDays] = useState<number | null>(null);

  useEffect(() => {
    lastTransactionAt().then((iso) => {
      if (!iso) return;
      const d = (Date.now() - new Date(iso).getTime()) / 86_400_000;
      setDays(d);
    }).catch(() => {});
  }, []);

  if (days === null || days < 3) return null;
  return (
    <div className="banner">
      ⚠️ No entra ninguna transacción desde hace {Math.floor(days)} días. Revisa el Atajo de
      iOS, el reenvío iCloud→Gmail o el Apps Script.
    </div>
  );
}
