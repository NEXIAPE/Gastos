# Guía de despliegue — Gastos

De cero a funcionando, **para tu propia copia privada**. Cada persona necesita
repetir esta guía con **su propia** cuenta de Supabase, Vercel, Gmail y banco —
no existe una versión "compartida" entre varias personas.

Las secciones **[A mano]** son configuración fuera de código (iPhone / iCloud /
Gmail) que haces tú, sin comandos.

> 💡 Si te trabas en algún paso (un error de la CLI, algo que no cuadra), la
> forma más rápida de resolverlo es pegar el error tal cual en una sesión de
> Claude Code — así se armó y depuró este proyecto la primera vez, paso a paso.

---

## 1. Crear el proyecto Supabase y la base de datos

1. Crea un proyecto en [supabase.com](https://supabase.com) (tier gratis),
   región cercana a ti (ej. South America - São Paulo para Perú).
2. En **SQL Editor**, pega y ejecuta **en orden** cada migración de
   [`supabase/migrations/`](../supabase/migrations/):
   1. `0001_init.sql` — tablas, RLS, índices, reglas de categorización semilla.
   2. `0002_more_category_rules.sql` — más reglas de comercios comunes.
   3. `0003_categories_table.sql` — tabla de categorías (editable desde el
      dashboard, sin volver a tocar SQL).
   4. `0004_more_categories.sql` — categorías adicionales sugeridas.
3. Anota de **Project Settings → API**:
   - `Project URL`  → `https://<PROJECT_REF>.supabase.co`
   - `anon public key` (para el dashboard)
   - `service_role key` (secreta, solo backend)

### Activar el login por magic link

En **Authentication → Providers → Email**: activa *Email* y *Magic Link*.
En **Authentication → URL Configuration** agrega la URL de tu dashboard
(la de Vercel del paso 4) a *Site URL* y *Redirect URLs*.

---

## 2. Desplegar las Edge Functions

Instala la [CLI de Supabase](https://supabase.com/docs/guides/cli) y enlaza:

```bash
supabase login
supabase link --project-ref <PROJECT_REF>
```

Define tus propios tokens secretos (cadenas largas y aleatorias) y guárdalos:

```bash
# Genera cada uno con, por ejemplo:  openssl rand -hex 24
supabase secrets set INGEST_TOKEN=<TU_TOKEN_LARGO_ALEATORIO>
supabase secrets set DIGEST_TOKEN=<OTRO_TOKEN_DISTINTO>
supabase secrets set DASHBOARD_URL=<URL_DE_TU_DASHBOARD_EN_VERCEL>
```

Despliega las funciones **imprescindibles**:

```bash
supabase functions deploy ingest
supabase functions deploy pending --no-verify-jwt
supabase functions deploy quick-categorize --no-verify-jwt
```

(`SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY` los inyecta Supabase solo.)
La config de `verify_jwt` por función está en
[`supabase/config.toml`](../supabase/config.toml).

Prueba el endpoint de ingesta:

```bash
curl -X POST https://<PROJECT_REF>.supabase.co/functions/v1/ingest \
  -H "Authorization: Bearer <TU_INGEST_TOKEN>" -H "Content-Type: application/json" \
  -d '{"source":"manual","channel":"tarjeta","direction":"out",
       "merchant":"TOTTUS SURCO","amount":84.50,"currency":"PEN"}'
# → {"status":"ok","deduped":false,"id":"..."}
```

### 🤖 [Opcional] Recomendaciones con IA

Por defecto, la página "Recomendaciones" del dashboard analiza tu data **sin
ninguna API** (gratis). Si además quieres que la API de Claude te genere
consejos en lenguaje natural cada semana:

```bash
supabase secrets set ANTHROPIC_API_KEY=<TU_API_KEY_DE_CLAUDE>
supabase functions deploy weekly-insights
```

Y programa el cron semanal con
[`supabase/scheduled_jobs.sql`](../supabase/scheduled_jobs.sql) (reemplaza
`<PROJECT_REF>` y `<SERVICE_ROLE_KEY>` ahí dentro).

---

## 3. Desplegar el dashboard

```bash
cd dashboard
cp .env.example .env.local      # rellena VITE_SUPABASE_URL y VITE_SUPABASE_ANON_KEY
npm install
npm run dev                     # local en http://localhost:5173
```

Para producción (Vercel/Netlify, tier gratis): conecta el repo, define el
*root directory* `dashboard`, build `npm run build`, output `dist`, y agrega las
variables `VITE_SUPABASE_URL` y `VITE_SUPABASE_ANON_KEY`. Solo la **anon key**
va al frontend (nunca el `service_role` ni ningún token de ingesta).

---

## 4. Apps Script de Gmail

Sigue [`apps-script/README.md`](../apps-script/README.md): pega `Code.gs` en
script.google.com y en *Script Properties* configura:

| Propiedad | Valor |
|---|---|
| `ENDPOINT_URL` | `https://<PROJECT_REF>.supabase.co/functions/v1/ingest` |
| `INGEST_TOKEN` | el mismo que pusiste como secret |
| `DIGEST_TOKEN` | el mismo que pusiste como secret |
| `DASHBOARD_URL` | la URL de tu dashboard en Vercel |

Luego ejecuta, una vez cada una:
- **`installTrigger`** → activa la lectura de correos cada 15 min.
- **`installDailyDigest`** → activa el correo diario "gastos por categorizar"
  con botones de 1 toque (~9pm). Puedes probarlo al toque ejecutando
  **`dailyDigest`** manualmente.

---

## 5. Atajo de iOS

Sigue [`ios-shortcut/README.md`](../ios-shortcut/README.md) para el Atajo de
Apple Pay (disparador "Transacción") y el atajo de "gasto en efectivo/Plin".

---

## 6. [A mano] Configuración de correos

- **Yape → correo:** app Yape → Ajustes → "Notificaciones por yapeo" → activar y
  poner el monto mínimo más bajo posible. (Solo yapeos > S/10 generan correo
  por defecto; algunos bancos como BCP notifican Yape desde S/1 si el yapeo se
  hace **desde la app del banco**.)
- **Plin / banco → correo:** en la banca de tu banco activa las **alertas de
  transacción por email** (consumos, pagos automáticos, etc.).
- **iCloud → Gmail:** en iCloud.com → Correo → Ajustes → Reglas, reenvía a Gmail
  los correos de tu(s) banco(s). Una regla por remitente.
- **Gmail:** crea un filtro por remitente (los de tu banco) que etiquete esos
  correos como **"Consumos"**.

---

## 7. Afinar las plantillas de parseo

Cuando tengas correos reales de tu banco (con datos sensibles tapados), ajusta
los regex del bloque `TEMPLATES` en `apps-script/Code.gs` — los que vienen son
para Interbank/BCP/Yape en Perú; otros bancos necesitarán su propia plantilla.
Mientras tanto, lo que no se parsee bien aparece en **Transacciones → Por
revisar** — nunca se pierde.

---

## 8. Personalización desde el dashboard (sin tocar código)

En **Ajustes** puedes, sin ningún comando:
- **Mis nombres** — para que las transferencias a ti mismo (ej. tu propio Plin)
  no cuenten como gasto.
- **Categorías** — agregar/borrar las que necesites; aparecen al toque en toda
  la app y en el correo diario.
- **Reglas de categorización**, **tipo de cambio fijo**, alta manual,
  recategorización masiva, import CSV y borrar todo.

---

## Verificación (criterios de aceptación)

- [ ] Un pago Apple Pay presencial aparece solo (Atajo).
- [ ] Un consumo/Yape/Plin aparece solo (correo del banco).
- [ ] Dinero recibido queda como `in` y **no** suma al gasto.
- [ ] Una transferencia a ti mismo (Ajustes → Mis nombres) queda como `transfer`.
- [ ] Una compra que llega por Apple Pay **y** correo del banco aparece **una vez**.
- [ ] El dashboard distingue el gasto por canal, categoría y tipo de gasto.
- [ ] Puedes recategorizar, crear reglas y agregar categorías propias.
- [ ] Te llega el correo diario de "gastos por categorizar" y categorizar con
      1 toque funciona.
