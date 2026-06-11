/**
 * Gastos — Parser de correos (Google Apps Script)
 * ------------------------------------------------------------------
 * Corre cada 10-15 min: lee la etiqueta "Consumos" de Gmail, detecta el tipo
 * de correo (Yape / Plin / Interbank / BCP), parsea con la plantilla
 * correspondiente y hace POST al endpoint /ingest. Solo marca un correo como
 * procesado DESPUÉS de un POST exitoso (HTTP 2xx); si falla, lo reintenta en la
 * siguiente corrida.
 *
 * CONFIGURA abajo ENDPOINT_URL y INGEST_TOKEN (Project Settings → Script
 * Properties es lo más seguro; aquí hay un fallback en código).
 *
 * Las plantillas de parseo están en el bloque TEMPLATES más abajo, separadas y
 * comentadas: AJÚSTALAS con tus correos reales de Yape, Plin y cada banco.
 */

// ===================== CONFIGURACIÓN =====================
function cfg(key, fallback) {
  var v = PropertiesService.getScriptProperties().getProperty(key);
  return v != null ? v : fallback;
}
var ENDPOINT_URL = cfg('ENDPOINT_URL', 'https://<PROJECT_REF>.supabase.co/functions/v1/ingest');
var INGEST_TOKEN = cfg('INGEST_TOKEN', 'PEGA_TU_TOKEN_AQUI');

var LABEL_IN   = 'Consumos';            // etiqueta de entrada
var LABEL_DONE = 'Consumos/Procesado';  // se aplica tras POST 2xx
var LABEL_ERR  = 'Consumos/Error';      // no se pudo parsear (revisar plantilla)
var MAX_THREADS_PER_RUN = 40;

// ===================== ENTRADA PRINCIPAL =====================
function processConsumos() {
  var inLabel = getOrCreateLabel(LABEL_IN);
  var doneLabel = getOrCreateLabel(LABEL_DONE);
  var errLabel = getOrCreateLabel(LABEL_ERR);

  var threads = inLabel.getThreads(0, MAX_THREADS_PER_RUN);
  for (var i = 0; i < threads.length; i++) {
    var thread = threads[i];
    var messages = thread.getMessages();
    var allOk = true;

    for (var j = 0; j < messages.length; j++) {
      var msg = messages[j];
      // Evita reprocesar mensajes ya marcados con un label propio del hilo.
      try {
        var parsed = parseMessage(msg);
        if (!parsed) {
          // No se reconoció: lo mandamos al endpoint como needs_review para no perderlo.
          parsed = fallbackNeedsReview(msg);
        }
        var ok = postIngest(parsed);
        if (!ok) allOk = false;
      } catch (e) {
        Logger.log('Error en mensaje ' + msg.getId() + ': ' + e);
        allOk = false;
      }
    }

    if (allOk) {
      thread.removeLabel(inLabel);
      thread.addLabel(doneLabel);
    } else {
      thread.addLabel(errLabel); // se reintentará en la próxima corrida (sigue en Consumos)
    }
  }
}

// ===================== POST AL ENDPOINT =====================
function postIngest(payload) {
  var options = {
    method: 'post',
    contentType: 'application/json',
    headers: { Authorization: 'Bearer ' + INGEST_TOKEN },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
  };
  var resp = UrlFetchApp.fetch(ENDPOINT_URL, options);
  var code = resp.getResponseCode();
  Logger.log('POST ' + code + ' ' + resp.getContentText());
  return code >= 200 && code < 300;
}

// ===================== DETECCIÓN DE TIPO =====================
function parseMessage(msg) {
  var from = msg.getFrom().toLowerCase();
  var subject = (msg.getSubject() || '');
  var body = msg.getPlainBody() || '';
  var date = msg.getDate(); // Date del correo
  var messageId = msg.getId();

  // Buscamos pistas en remitente + asunto + cuerpo. Esto resiste el reenvío de
  // iCloud (que a veces reescribe el "De:"): aunque el remitente cambie, el
  // asunto/cuerpo conservan "Interbank" / "BCP" / "Yape".
  var hay = (from + ' ' + subject + ' ' + body).toLowerCase();

  // Yape primero (su correo es inconfundible).
  if (hay.indexOf('yape') !== -1) {
    return TEMPLATES.yape(body, subject, date, messageId);
  }

  // ¿Qué banco es? (netinterbank.com.pe contiene "interbank"; notificacionesbcp contiene "bcp")
  var bank = (hay.indexOf('interbank') !== -1) ? 'interbank'
           : ((hay.indexOf('bcp') !== -1 || hay.indexOf('viabcp') !== -1) ? 'bcp' : null);
  if (!bank) return null; // desconocido → irá a "Por revisar"

  // Pago Automático de servicios (Luz del Sur, etc.) — viene de
  // pagoautomatico@notificaciones.interbank.pe y trae "Empresa: 006 - LUZ DEL SUR".
  if (bank === 'interbank' && (hay.indexOf('pago autom') !== -1 || from.indexOf('pagoautomatico') !== -1)) {
    return TEMPLATES.pagoAutomatico(body, subject, date, messageId);
  }

  // ¿Es un Plin? Marcador fuerte en el CUERPO ("PLIN-Nombre" / "Empresa PLIN").
  // OJO: no usamos "plin" suelto porque los correos de Interbank mencionan
  // "plin.pe" en el pie de página de seguridad (falso positivo).
  var isPlin = /plin\s*-|empresa\s+plin/i.test(body);
  if (isPlin) return TEMPLATES.plin(body, subject, date, messageId, bank);

  return bank === 'interbank'
    ? TEMPLATES.interbank(body, subject, date, messageId)
    : TEMPLATES.bcp(body, subject, date, messageId);
}

// ===================== HELPERS DE PARSEO =====================
function toIsoLima(date) {
  // Formatea la fecha del correo en zona America/Lima (UTC-5).
  return Utilities.formatDate(date, 'America/Lima', "yyyy-MM-dd'T'HH:mm:ssXXX");
}

function parseAmount(str) {
  if (!str) return null;
  // Quita separadores de miles y normaliza decimal.
  var n = String(str).replace(/[^0-9.,]/g, '').replace(/,(?=\d{3}\b)/g, '').replace(',', '.');
  var f = parseFloat(n);
  return isFinite(f) ? f : null;
}

// Estado a partir del ASUNTO (limpio), no del cuerpo (que trae pies de página
// legales con palabras como "devolución" que causarían falsos reembolsos).
function statusFromSubject(subject) {
  var s = (subject || '').toLowerCase();
  if (/rechaz|denegad|no procesada/.test(s)) return 'declined';
  if (/extorno|anulaci|reverso|reversad/.test(s)) return 'reversed';
  if (/reembolso|devoluci/.test(s)) return 'refunded';
  return 'confirmed';
}

function detectCurrency(str) {
  if (!str) return 'PEN';
  if (/US\$|USD|\$\s*\d/.test(str)) return 'USD';
  return 'PEN';
}

function firstMatch(text, regexes) {
  for (var i = 0; i < regexes.length; i++) {
    var m = text.match(regexes[i]);
    if (m) return m;
  }
  return null;
}

function fallbackNeedsReview(msg) {
  return {
    source: 'manual',
    channel: null,
    status: 'needs_review',
    occurred_at: toIsoLima(msg.getDate()),
    merchant: '(correo sin parsear) ' + (msg.getSubject() || ''),
    amount: 0,
    currency: 'PEN',
    external_ref: 'gmail:' + msg.getId(),
    text: msg.getPlainBody() || '',
    notes: 'Parser no reconoció este correo. Revisar plantilla / corregir a mano.',
  };
}

/* =====================================================================
 *  TEMPLATES — AJÚSTALAS CON TUS CORREOS REALES
 *  ---------------------------------------------------------------------
 *  Cada función recibe (body, subject, date, messageId[, from]) y devuelve
 *  el objeto JSON para /ingest. Los regex de ejemplo son aproximados:
 *  pega un correo real de cada tipo y afina los patrones de monto, comercio,
 *  contraparte y nro. de operación. Mientras un campo no se encuentre, el
 *  endpoint marcará la transacción como needs_review (no se pierde nada).
 *
 *  Campos del payload:
 *   source:   email_yape | email_plin | email_interbank | email_bcp
 *   channel:  yape | plin | tarjeta
 *   direction: out | in | transfer   (si lo omites, el endpoint lo infiere del `text`)
 *   status:    confirmed | declined | reversed | refunded  (idem, se infiere)
 *   external_ref: nro. de operación/voucher si existe; si no, 'gmail:'+messageId
 * ===================================================================== */
// Monto: maneja "S/ 10.00" y "S/. 3.90" (Interbank usa "S/.").
var AMOUNT_RE = [/US\$\.?\s*([\d.,]+)/i, /S\/\.?\s*([\d.,]+)/i];
// Tarjeta enmascarada: 4 dígitos tras los asteriscos ("****9251", "************2730").
var CARD_RE = [/\*{2,}\s*(\d{4})/];
// Voucher: SOLO "Número de operación NNN" (evita confundir con los 4 díg. de tarjeta).
var VOUCHER_RE = [/n[uú]mero\s+de\s+operaci[oó]n\D*?(\d{4,})/i];

var TEMPLATES = {

  // -------------------- YAPE --------------------
  // (Aún sin muestra real: ajustar cuando llegue un correo de Yape.)
  // Correo solo para yapeos > S/10. Llega cuando pagas Y cuando te yapean.
  yape: function (body, subject, date, messageId) {
    var amountM = firstMatch(body, AMOUNT_RE);
    var who = firstMatch(body, [
      /(?:a|para)\s+([A-ZÁÉÍÓÚÑ][\w .'-]{2,40})/,
      /(?:de|recibiste de)\s+([A-ZÁÉÍÓÚÑ][\w .'-]{2,40})/,
    ]);
    var voucher = firstMatch(body, VOUCHER_RE);
    return {
      source: 'email_yape',
      channel: 'yape',
      // direction la infiere el endpoint del `text` (pagaste/te yapearon/etc.).
      status: statusFromSubject(subject),
      occurred_at: toIsoLima(date),
      merchant: who ? who[1].trim() : 'Yape',
      counterparty: who ? who[1].trim() : null,
      amount: amountM ? parseAmount(amountM[1]) : 0,
      currency: 'PEN',
      external_ref: voucher ? 'yape:' + voucher[1] : 'gmail:' + messageId,
      text: subject + ' ' + body,
    };
  },

  // -------------------- PLIN (vía alerta del banco BCP/Interbank) --------------------
  // Muestra real BCP: "...con tu Tarjeta de Débito BCP en PLIN-Alessandra Sanche",
  // "Empresa  PLIN-Alessandra Sanche", "Número de operación  741981".
  plin: function (body, subject, date, messageId, bank) {
    var amountM = firstMatch(body, AMOUNT_RE);
    var who = firstMatch(body, [
      /Empresa\s+([^\n\r]+)/i,
      /\ben\s+(PLIN[-\s][^\n\r.]+)/i,
    ]);
    var voucher = firstMatch(body, VOUCHER_RE);
    return {
      source: bank === 'interbank' ? 'email_interbank' : 'email_bcp',
      channel: 'plin',
      direction: 'out', // "Realizaste un consumo" = pago saliente (el endpoint lo
                        // reclasifica a 'transfer' si la contraparte eres tú).
      status: statusFromSubject(subject),
      occurred_at: toIsoLima(date),
      merchant: who ? who[1].trim() : 'Plin',
      counterparty: who ? who[1].trim() : null,
      amount: amountM ? parseAmount(amountM[1]) : 0,
      currency: detectCurrency(body),
      external_ref: voucher ? 'plin:' + voucher[1] : 'gmail:' + messageId,
      text: subject + ' ' + body,
    };
  },

  // -------------------- INTERBANK · PAGO AUTOMÁTICO de servicios --------------------
  // Muestra real: "Empresa: 006 - LUZ DEL SUR", "Monto cobrado: S/ 146.40".
  // El "Código cliente" NO es único por mes → external_ref = id del correo.
  pagoAutomatico: function (body, subject, date, messageId) {
    var amountM = firstMatch(body, [/Monto\s+cobrado:?\s*S\/\.?\s*([\d.,]+)/i]) || firstMatch(body, AMOUNT_RE);
    var merch = firstMatch(body, [
      /Empresa:?\s*\d*\s*-\s*([^\n\r]+)/i,
      /Servicio:?\s*\d*\s*-\s*([^\n\r]+)/i,
    ]);
    return {
      source: 'email_interbank',
      channel: 'tarjeta',
      direction: 'out',
      status: statusFromSubject(subject),
      occurred_at: toIsoLima(date),
      merchant: merch ? merch[1].trim() : 'Pago automático Interbank',
      amount: amountM ? parseAmount(amountM[1]) : 0,
      currency: detectCurrency(body),
      external_ref: 'gmail:' + messageId,
      notes: 'Pago automático',
      text: subject + ' ' + body,
    };
  },

  // -------------------- INTERBANK (tarjeta / consumo) --------------------
  // Muestra real: "Comercio: OXXO TAMAYO", "Monto: S/. 3.90", "Tarjeta: ****9251".
  interbank: function (body, subject, date, messageId) {
    var amountM = firstMatch(body, AMOUNT_RE);
    var merch = firstMatch(body, [
      /Comercio:\s*([^\n\r]+)/i,
      /\ben\s+([A-Z0-9][\w &.'*\/-]{2,40})/,
    ]);
    var card = firstMatch(body, CARD_RE);
    var voucher = firstMatch(body, VOUCHER_RE);
    return {
      source: 'email_interbank',
      channel: 'tarjeta',
      direction: 'out',
      status: statusFromSubject(subject),
      occurred_at: toIsoLima(date),
      merchant: merch ? merch[1].trim() : (subject || 'Interbank'),
      amount: amountM ? parseAmount(amountM[1]) : 0,
      currency: detectCurrency(body),
      card_label: card ? 'Interbank ****' + card[1] : 'Interbank',
      external_ref: voucher ? 'ibk:' + voucher[1] : 'gmail:' + messageId,
      text: subject + ' ' + body,
    };
  },

  // -------------------- BCP (tarjeta / consumo, no Plin) --------------------
  // Muestra real: "Realizaste un consumo de S/ 10.00 con tu Tarjeta de Débito BCP en <COMERCIO>".
  bcp: function (body, subject, date, messageId) {
    var amountM = firstMatch(body, AMOUNT_RE);
    var merch = firstMatch(body, [
      /Tarjeta de D[eé]bito BCP en\s+([^\n\r.]+)/i,
      /Comercio:?\s*([^\n\r]+)/i,
      /\ben\s+([A-Z0-9][\w &.'*\/-]{2,40})/,
    ]);
    var card = firstMatch(body, CARD_RE);
    var voucher = firstMatch(body, VOUCHER_RE);
    return {
      source: 'email_bcp',
      channel: 'tarjeta',
      direction: 'out',
      status: statusFromSubject(subject),
      occurred_at: toIsoLima(date),
      merchant: merch ? merch[1].trim() : (subject || 'BCP'),
      amount: amountM ? parseAmount(amountM[1]) : 0,
      currency: detectCurrency(body),
      card_label: card ? 'BCP ****' + card[1] : 'BCP',
      external_ref: voucher ? 'bcp:' + voucher[1] : 'gmail:' + messageId,
      text: subject + ' ' + body,
    };
  },
};

// ===================== UTILIDADES GMAIL =====================
function getOrCreateLabel(name) {
  var label = GmailApp.getUserLabelByName(name);
  return label ? label : GmailApp.createLabel(name);
}

// ===================== INSTALADOR DEL TRIGGER =====================
// Ejecuta esta función UNA vez para crear el disparador cada 15 minutos.
function installTrigger() {
  var triggers = ScriptApp.getProjectTriggers();
  for (var i = 0; i < triggers.length; i++) {
    if (triggers[i].getHandlerFunction() === 'processConsumos') {
      ScriptApp.deleteTrigger(triggers[i]);
    }
  }
  ScriptApp.newTrigger('processConsumos').timeBased().everyMinutes(15).create();
  Logger.log('Trigger instalado: processConsumos cada 15 min.');
}
