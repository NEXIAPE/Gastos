import { useEffect, useState } from "react";
import { Route, Routes } from "react-router-dom";
import type { Session } from "@supabase/supabase-js";
import { supabase } from "./lib/supabase";
import Auth from "./components/Auth";
import Layout from "./components/Layout";
import Resumen from "./pages/Resumen";
import Tendencia from "./pages/Tendencia";
import TopComercios from "./pages/TopComercios";
import PorCategoria from "./pages/PorCategoria";
import PorCanal from "./pages/PorCanal";
import Transacciones from "./pages/Transacciones";
import PorRevisar from "./pages/PorRevisar";
import Recibido from "./pages/Recibido";
import Insights from "./pages/Insights";
import Ajustes from "./pages/Ajustes";

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
  if (!session) return <Auth />;

  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Resumen />} />
        <Route path="/tendencia" element={<Tendencia />} />
        <Route path="/comercios" element={<TopComercios />} />
        <Route path="/categorias" element={<PorCategoria />} />
        <Route path="/canal" element={<PorCanal />} />
        <Route path="/transacciones" element={<Transacciones />} />
        <Route path="/revisar" element={<PorRevisar />} />
        <Route path="/recibido" element={<Recibido />} />
        <Route path="/insights" element={<Insights />} />
        <Route path="/ajustes" element={<Ajustes />} />
      </Route>
    </Routes>
  );
}
