# Gastos — Sistema personal de tracking de consumos

Sistema automatizado que captura cada consumo (Apple Pay, Yape, Plin, tarjeta) y
muestra un **dashboard de gastos por categoría, mes y comercio**, con
recomendaciones semanales generadas por IA.

Bancos: **Interbank** y **BCP** (Perú). Moneda base de reportes: **S/ (PEN)**.

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
        Dashboard React/Vite (login magic-link)  +  Insights IA (Claude)
```

## Estructura del repositorio

| Carpeta | Qué es |
|---------|--------|
| `supabase/migrations/` | Esquema SQL (tablas, RLS, índices, reglas semilla). |
| `supabase/functions/ingest/` | Edge Function de ingesta (token, dedup, categorización). |
| `supabase/functions/weekly-insights/` | Edge Function que genera recomendaciones con la API de Claude. |
| `apps-script/` | Google Apps Script que parsea Gmail y postea al endpoint. |
| `ios-shortcut/` | Instrucciones paso a paso para el Atajo de Apple Pay. |
| `dashboard/` | App web React + Vite (todas las vistas del dashboard). |
| `docs/SETUP.md` | Guía de despliegue de punta a punta. |

## Puesta en marcha (resumen)

Sigue la guía completa en **[`docs/SETUP.md`](docs/SETUP.md)**. En orden:

1. Crear proyecto Supabase y aplicar la migración (`supabase/migrations`).
2. Desplegar las Edge Functions `ingest` y `weekly-insights`, con sus secrets.
3. Desplegar el dashboard (Vercel/Netlify) con las variables `VITE_*`.
4. Pegar el Apps Script en script.google.com y configurar el trigger.
5. Crear el Atajo de iOS.
6. Configuración manual de correos (iCloud → Gmail, etiqueta "Consumos").

## Decisiones de diseño confirmadas

- **Stack:** Supabase (Postgres + Edge Functions) + dashboard React/Vite.
- **Tipo de cambio USD→PEN:** valor **fijo configurable** desde el dashboard
  (tabla `settings`, clave `fx_usd_pen`). Si el correo ya trae el monto en soles,
  se usa ese.
- **Recomendaciones IA:** API de Claude (Sonnet) desde la v1, vía el secret
  `ANTHROPIC_API_KEY` del backend (nunca en el frontend).
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
