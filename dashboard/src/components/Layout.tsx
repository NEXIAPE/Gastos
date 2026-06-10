import { NavLink, Outlet } from "react-router-dom";
import { supabase } from "../lib/supabase";
import HealthBanner from "./HealthBanner";

const links: [string, string][] = [
  ["/", "Resumen del mes"],
  ["/tendencia", "Tendencia mensual"],
  ["/comercios", "Top comercios"],
  ["/categorias", "Por categoría"],
  ["/canal", "Por canal"],
  ["/transacciones", "Transacciones"],
  ["/revisar", "Por revisar"],
  ["/recibido", "Dinero recibido"],
  ["/insights", "Recomendaciones"],
  ["/ajustes", "Ajustes"],
];

export default function Layout() {
  return (
    <div className="app">
      <aside className="sidebar">
        <h1>Gastos</h1>
        <nav className="nav">
          {links.map(([to, label]) => (
            <NavLink key={to} to={to} end={to === "/"}>{label}</NavLink>
          ))}
        </nav>
        <div style={{ padding: "16px 20px" }}>
          <button className="link" onClick={() => supabase.auth.signOut()}>Cerrar sesión</button>
        </div>
      </aside>
      <main className="main">
        <HealthBanner />
        <Outlet />
      </main>
    </div>
  );
}
