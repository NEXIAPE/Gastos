import { useEffect, useState } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "./lib/supabase";
import Auth from "./components/Auth";
import Layout from "./components/Layout";
import Resumen from "./pages/Resumen";
import Analisis from "./pages/Analisis";
import Transacciones from "./pages/Transacciones";
import Presupuestos from "./pages/Presupuestos";
import Insights from "./pages/Insights";
import Ajustes from "./pages/Ajustes";

// ⚠️ TEMPORAL: login desactivado a pedido explícito (sin acceso al correo del
// enlace mágico). El dashboard queda accesible por link a cualquiera mientras
// esto sea `false`. Vuelve a poner `true` en cuanto tengas acceso a tu correo.
const REQUIRE_LOGIN = false;

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setReady(true);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => sub.subscription.unsubscribe();
  }, []);

  if (!ready) return <div className="center">Cargando…</div>;
  if (REQUIRE_LOGIN && !session) return <Auth />;

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Resumen />} />
        <Route path="/analisis" element={<Analisis />} />
        <Route path="/transacciones" element={<Transacciones />} />
        <Route path="/presupuestos" element={<Presupuestos />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/ajustes" element={<Ajustes />} />
        {/* Rutas antiguas → redirigen a las nuevas vistas consolidadas */}
        <Route path="/tendencia" element={<Navigate to="/analisis" replace />} />
        <Route path="/comercios" element={<Navigate to="/analisis" replace />} />
        <Route path="/categorias" element={<Navigate to="/analisis" replace />} />
        <Route path="/canal" element={<Navigate to="/analisis" replace />} />
        <Route path="/revisar" element={<Navigate to="/transacciones" replace />} />
        <Route path="/recibido" element={<Navigate to="/transacciones" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
