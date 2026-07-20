# Gastos — Sistema personal de tracking de consumos

Sistema automatizado que captura cada consumo (Apple Pay, Yape, Plin, tarjeta) y
muestra un **dashboard de gastos por categoría, mes y comercio**, con
recomendaciones semanales generadas por IA.

Bancos: **Interbank** y **BCP** (Perú). Moneda base de reportes: **S/ (PEN)**.

> 🔒 **¿Quieres tu propia copia (privada)?** Cada persona necesita su propio
> despliegue: proyecto Supabase, dashboard y Apps Script propios, conectados a
> **sus propios** correos de banco. No hay una versión "compartida" donde varias
> personas inicien sesión — así tus datos financieros nunca se mezclan ni se ven
> entre sí. Sigue **[`docs/SETUP.md`](docs/SETUP.md)** de punta a punta; es largo
> pero cada paso está detallado. Si te trabas en algún paso técnico (la CLI,
> algún error), pega el mensaje de error tal cual en una sesión de Claude Code —
> así se armó y depuró este proyecto la primera vez.

```
  Apple Pay presencial            Yape / Plin / tarjeta / banco
  (Atajo iOS "Transacción")       (correos → iCloud → Gmail, etiqueta "Consumos")
            │                                   │
            │ POST JSON                         │ Apps Script lee Gmail cada 10-15 min,
            ▼                                   ▼ detecta tipo, parsea y hace POST JSON
        ┌─────────────────────────────────────────────────────┐
        │   Edge Function  /ingest  (token secreto)            │
        │   valida token · normaliza · categoriza · deduplica  │
        └─────────────────────────────────────────────────────┘
                              │
                              ▼
                    Supabase Postgres (transactions, …)  ── RLS
                              │
                              ▼
        Dashboard React/Vite (login magic-link) + correo diario de categorización
```

## Estructura del repositorio

| Carpeta | Qué es |
|---------|--------|
| `supabase/migrations/` | Esquema SQL (tablas, RLS, índices, reglas y categorías semilla). |
| `supabase/functions/ingest/` | Edge Function de ingesta (token, dedup, categorización). |
| `supabase/functions/pending/` + `quick-categorize/` | Correo diario "por categorizar" con botones de 1 toque. |
| `supabase/functions/weekly-insights/` | *(Opcional)* recomendaciones con la API de Claude. |
| `apps-script/` | Google Apps Script que parsea Gmail y postea al endpoint. |
| `ios-shortcut/` | Instrucciones paso a paso para el Atajo de Apple Pay. |
| `dashboard/` | App web React + Vite (todas las vistas del dashboard). |
| `docs/SETUP.md` | Guía de despliegue de punta a punta (tu propia copia privada). |

## Puesta en marcha (resumen)

Sigue la guía completa en **[`docs/SETUP.md`](docs/SETUP.md)**. En orden:

1. Crear proyecto Supabase y aplicar las migraciones (`supabase/migrations`).
2. Desplegar las Edge Functions `ingest`, `pending` y `quick-categorize`, con sus secrets.
3. Desplegar el dashboard (Vercel/Netlify) con las variables `VITE_*`.
4. Pegar el Apps Script en script.google.com y activar los dos triggers (lectura de correos + correo diario).
5. Crear el Atajo de iOS.
6. Configuración manual de correos (iCloud → Gmail, etiqueta "Consumos").
7. Personalizar desde Ajustes: tus nombres, categorías, tipo de cambio.

## Decisiones de diseño confirmadas

- **Stack:** Supabase (Postgres + Edge Functions) + dashboard React/Vite.
- **Tipo de cambio USD→PEN:** valor **fijo configurable** desde el dashboard
  (tabla `settings`, clave `fx_usd_pen`). Si el correo ya trae el monto en soles,
  se usa ese.
- **Recomendaciones:** por defecto, análisis local de tu propia data (sin
  ninguna API, gratis). Opcionalmente se puede sumar la API de Claude
  (`ANTHROPIC_API_KEY` del backend, nunca en el frontend) — ver `docs/SETUP.md`.
- **Categorías:** dinámicas, en la tabla `categories`; se agregan/borran desde
  Ajustes, sin tocar código.
- **Login:** magic link por correo (Supabase Auth).
- **Zona horaria:** `America/Lima` (UTC-5, sin horario de verano) para todos los
  cortes de día/mes.

## Reglas de negocio clave (para no contar mal)

- Solo `direction = 'out'` **y** `status = 'confirmed'` cuentan como gasto.
- `in` (dinero recibido) y `transfer` (entre cuentas propias / recargas) se
  guardan pero **no** suman al gasto.
- Reembolsos/extornos (`refunded`/`reversed`) se restan del gasto neto.
- Lo que el parser no entiende se guarda como `needs_review` — nunca se pierde.
- Deduplicación por `external_ref` (idempotente); fallback por
  monto+moneda+comercio+ventana ±60 min **solo entre fuentes distintas**.
