# Guía de despliegue — Gastos

De cero a funcionando. Las secciones **[A mano]** son configuración fuera de
código (iPhone / iCloud / Gmail) que haces tú.

---

## 1. Crear el proyecto Supabase y la base de datos

1. Crea un proyecto en [supabase.com](https://supabase.com) (tier gratis).
2. En **SQL Editor**, pega y ejecuta el contenido de
   [`supabase/migrations/0001_init.sql`](../supabase/migrations/0001_init.sql).
   Esto crea las tablas, índices, RLS y siembra las reglas de categorización.
3. Anota de **Project Settings → API**:
   - `Project URL`  → `https://<PROJECT_REF>.supabase.co`
   - `anon public key` (para el dashboard)
   - `service_role key` (secreta, solo backend)

### Activar el login por magic link

En **Authentication → Providers → Email**: activa *Email* y *Magic Link*.
En **Authentication → URL Configuration** agrega la URL del dashboard
(ej. `https://gastos.vercel.app`) a *Site URL* y *Redirect URLs*.

---

## 2. Desplegar las Edge Functions

Instala la [CLI de Supabase](https://supabase.com/docs/guides/cli) y enlaza:

```bash
supabase login
supabase link --project-ref <PROJECT_REF>
```

Define un **token de ingesta** propio (cadena larga y aleatoria) y los secrets:

```bash
# Genera un token (ejemplo):  openssl rand -hex 32
supabase secrets set INGEST_TOKEN=<TU_TOKEN_LARGO_ALEATORIO>
supabase secrets set ANTHROPIC_API_KEY=<TU_API_KEY_DE_CLAUDE>
# Opcional, default claude-sonnet-4-6:
supabase secrets set INSIGHTS_MODEL=claude-sonnet-4-6
```

Despliega:

```bash
supabase functions deploy ingest
supabase functions deploy weekly-insights
```

(`SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` los inyecta Supabase solo.)
La config de `verify_jwt` por función está en
[`supabase/config.toml`](../supabase/config.toml).

Prueba el endpoint:

```bash
curl -X POST https://<PROJECT_REF>.supabase.co/functions/v1/ingest \
  -H "Authorization: Bearer <TU_TOKEN>" -H "Content-Type: application/json" \
  -d '{"source":"manual","channel":"tarjeta","direction":"out",
       "merchant":"TOTTUS SURCO","amount":84.50,"currency":"PEN"}'
# → {"status":"ok","deduped":false,"id":"..."}
```

---

## 3. Programar las recomendaciones semanales (cron)

En el **SQL Editor**, ejecuta
[`supabase/scheduled_jobs.sql`](../supabase/scheduled_jobs.sql) reemplazando
`<PROJECT_REF>` y `<SERVICE_ROLE_KEY>`. Corre cada lunes 08:00 (hora Lima).
También puedes generar bajo demanda con el botón "Regenerar" del dashboard.

---

## 4. Desplegar el dashboard

```bash
cd dashboard
cp .env.example .env.local      # rellena VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY
npm install
npm run dev                     # local en http://localhost:5173
```

Para producción (Vercel/Netlify, tier gratis): conecta el repo, define el
*root directory* `dashboard`, build `npm run build`, output `dist`, y agrega las
variables `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY`. Solo la **anon key**
va al frontend (nunca el service_role ni el INGEST_TOKEN).

---

## 5. Apps Script de Gmail

Sigue [`apps-script/README.md`](../apps-script/README.md): pega `Code.gs` en
script.google.com, configura `ENDPOINT_URL` e `INGEST_TOKEN` en *Script
Properties*, y ejecuta `installTrigger` (cada 15 min).

---

## 6. Atajo de iOS

Sigue [`ios-shortcut/README.md`](../ios-shortcut/README.md) para el Atajo de
Apple Pay (disparador "Transacción") y el atajo de "gasto en efectivo".

---

## 7. [A mano] Configuración de correos

- **Yape → correo:** app Yape → Ajustes → "Notificaciones por yapeo" → activar y
  poner el monto mínimo más bajo posible. (Solo yapeos > S/10 generan correo.)
- **Plin / banco → correo:** en la banca de Interbank y BCP activa las **alertas
  de transacción por email**.
- **iCloud → Gmail:** en iCloud.com → Correo → Ajustes → Reglas, reenvía a Gmail
  los correos de Interbank, BCP y Yape.
- **Gmail:** crea un filtro que etiquete esos correos como **"Consumos"**.

---

## 8. Afinar las plantillas de parseo

Cuando tengas correos reales (uno de Yape, Plin, Interbank y BCP, con datos
sensibles tapados), ajusta los regex del bloque `TEMPLATES` en
`apps-script/Code.gs`. Mientras tanto, lo que no se parsee bien aparece en la
vista **"Por revisar"** del dashboard — nunca se pierde.

---

## Verificación (criterios de aceptación)

- [ ] Un pago Apple Pay presencial aparece solo (Atajo).
- [ ] Un yapeo > S/10 aparece solo (correo Yape).
- [ ] Un Plin aparece solo (alerta del banco).
- [ ] Dinero recibido por Yape/Plin queda como `in` y **no** suma al gasto.
- [ ] Una compra que llega por Apple Pay **y** correo del banco aparece **una vez**.
- [ ] El dashboard distingue el gasto por canal y por categoría.
- [ ] Puedes recategorizar y crear reglas.
- [ ] Existen las categorías **Luna** y **Antojos**.
- [ ] Cada semana hay una recomendación nueva (y botón para regenerar).
