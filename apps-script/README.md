# Apps Script — Parser de correos Gmail

Lee la etiqueta **Consumos** de Gmail cada 15 min, detecta el tipo de correo
(Yape / Plin / Interbank / BCP), lo parsea y hace `POST` a `/ingest`.

## Instalación

1. Ve a [script.google.com](https://script.google.com) → **Nuevo proyecto**.
2. Pega el contenido de [`Code.gs`](Code.gs).
3. **Configura los secrets** en *Project Settings → Script Properties*:
   - `ENDPOINT_URL` → `https://<PROJECT_REF>.supabase.co/functions/v1/ingest`
   - `INGEST_TOKEN` → el mismo token que pusiste como secret en Supabase.
4. Ejecuta una vez la función **`installTrigger`** (autoriza los permisos de
   Gmail/UrlFetch que pida). Eso crea el disparador cada 15 minutos.
5. Para probar manualmente: ejecuta **`processConsumos`** y revisa *Ejecuciones*
   y los `Logger.log`.

## Cómo funciona (confiabilidad)

- Un correo solo se marca como procesado (etiqueta `Consumos/Procesado`)
  **después** de un POST con HTTP 2xx. Si falla, el hilo queda etiquetado
  `Consumos/Error` pero **sigue** en `Consumos` y se reintenta en la siguiente
  corrida → **nunca se pierde un movimiento**.
- Un correo que no se reconoce no se descarta: se envía al endpoint como
  `status = needs_review` para que aparezca en la bandeja "Por revisar" del
  dashboard.
- `external_ref` usa el nº de operación/voucher si el correo lo trae; si no,
  usa el ID del mensaje de Gmail. Eso hace el POST **idempotente** (reenviar el
  mismo correo no duplica).

## Ajustar las plantillas (importante)

Los regex del bloque `TEMPLATES` en `Code.gs` son **aproximados**. Para afinarlos:

1. Abre un correo real de cada tipo (Yape, Plin, Interbank, BCP).
2. Copia el texto (`getPlainBody`) y ajusta los patrones de:
   - **monto** (`S/`, `US$`),
   - **comercio / contraparte**,
   - **nº de operación / voucher** (clave para deduplicar),
   - palabras de **dirección** (pagaste/te yapearon…) y **estado**
     (rechazada, extorno, reembolso) — estas las interpreta el endpoint a
     partir del campo `text`, así que basta con enviar el cuerpo completo.

Mientras un campo no se encuentre, el endpoint marca la transacción como
`needs_review`: la corriges desde el dashboard y, si quieres, creas una regla.

> Recuerda: **Yape solo envía correo para yapeos > S/10**. Los menores se cubren
> con registro manual o con la reconciliación mensual contra el estado BCP.
