# Atajo de iOS — Apple Pay presencial (disparador "Transacción")

Captura los pagos **NFC presenciales** con Apple Pay en tiempo real y los manda
al endpoint `/ingest`. (No captura Apple Pay online, ni Yape, ni Plin: eso llega
por correo.) El disparador a veces falla por timeout — por eso el correo del
banco es el respaldo.

## A. Crear la automatización (iOS 17+)

1. App **Atajos** → pestaña **Automatización** → **+** → **Crear automatización personal**.
2. Elige el disparador **"Transacción"**.
3. Selecciona **las tarjetas** de Apple Wallet que quieres rastrear (Interbank,
   BCP, etc.).
4. Marca **"Ejecutar inmediatamente"** (sin preguntar).
5. **Añadir acción** → continúa con el flujo de abajo.

## B. Acciones del atajo

> El disparador "Transacción" entrega variables: **Comercio**, **Monto**,
> **Moneda**, **Fecha** y **Tarjeta**. Úsalas en el diccionario.

1. **Obtener fecha actual** (o usa la variable *Fecha* de la transacción).
2. **Texto** → escribe la fecha en formato ISO con zona de Lima, o usa
   *Formato de fecha* → personalizado: `yyyy-MM-dd'T'HH:mm:ssZZZZZ`.
3. **Diccionario** con estas claves:

   | Clave         | Valor (variable del disparador)        |
   |---------------|----------------------------------------|
   | `source`      | `apple_pay_shortcut` (texto fijo)      |
   | `channel`     | `apple_pay` (texto fijo)               |
   | `direction`   | `out` (texto fijo)                     |
   | `occurred_at` | la Fecha en ISO del paso anterior      |
   | `merchant`    | variable **Comercio**                  |
   | `amount`      | variable **Monto**                     |
   | `currency`    | variable **Moneda** (o `PEN` fijo)     |
   | `card_label`  | variable **Tarjeta** (o etiqueta fija) |

4. **Obtener contenido de URL**:
   - URL: `https://<PROJECT_REF>.supabase.co/functions/v1/ingest`
   - Método: **POST**
   - **Encabezados**:
     - `Authorization` = `Bearer <TU_INGEST_TOKEN>`
     - `Content-Type` = `application/json`
   - **Cuerpo de la solicitud**: **JSON** → selecciona el **Diccionario** del paso 3.

5. (Opcional) **Mostrar notificación** con el resultado para confirmar que entró.

## C. Notas

- El disparador **se dispara incluso si la compra es rechazada**. No te
  preocupes: el correo del banco que llega después trae el estado real
  (`declined`/`reversed`) y el endpoint fusiona ambos por la ventana de ±60 min,
  dejando el estado correcto. Aun así, si quieres, puedes añadir lógica en el
  atajo para no enviar montos en 0.
- Si el monto viene en **USD**, el endpoint lo convierte a soles con el tipo de
  cambio fijo configurado en el dashboard.

## D. Atajo extra: "Registrar gasto en efectivo"

Un segundo atajo manual (sin disparador) para efectivo y yapeos < S/10:

1. **Pedir entrada** (Número) → "¿Cuánto gastaste?" → variable *Monto*.
2. **Pedir entrada** (Texto) → "¿En qué/dónde?" → variable *Comercio*.
3. **Diccionario**: `source=manual`, `channel=efectivo`, `direction=out`,
   `merchant`=Comercio, `amount`=Monto, `currency=PEN`.
4. **Obtener contenido de URL** → POST al mismo endpoint con el header
   `Authorization: Bearer <TU_INGEST_TOKEN>`.
5. Añádelo a la pantalla de inicio para registrar en 5 segundos.
