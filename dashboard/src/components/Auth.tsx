import { useState } from "react";
import { supabase } from "../lib/supabase";

export default function Auth() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function sendLink(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setLoading(true);
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: window.location.origin },
    });
    setLoading(false);
    if (error) setErr(error.message);
    else setSent(true);
  }

  return (
    <div className="center">
      <div className="auth-box">
        <h1>Gastos</h1>
        {sent ? (
          <p className="muted">
            Te enviamos un enlace de acceso a <b>{email}</b>. Ábrelo en este dispositivo
            para entrar.
          </p>
        ) : (
          <form onSubmit={sendLink}>
            <p className="muted">Ingresa con tu correo (recibirás un enlace mágico).</p>
            <div className="field">
              <label>Correo</label>
              <input
                type="email" required value={email} style={{ width: "100%" }}
                onChange={(e) => setEmail(e.target.value)} placeholder="tu@correo.com"
              />
            </div>
            {err && <p className="neg">{err}</p>}
            <button className="primary" disabled={loading} style={{ width: "100%" }}>
              {loading ? "Enviando…" : "Enviar enlace"}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
