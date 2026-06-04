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

  if (from.indexOf('yape') !== -1 || subject.toLowerCase().indexOf('yape') !== -1) {
    return TEMPLATES.yape(body, subject, date, messageId);
  }
  if (subject.toLowerCase().indexOf('plin') !== -1 || body.toLowerCase().indexOf('plin') !== -1) {
    return TEMPLATES.plin(body, subject, date, messageId, from);
  }
  if (from.indexOf('interbank') !== -1) {
    return TEMPLATES.interbank(body, subject, date, messageId);
  }
  if (from.indexOf('bcp') !== -1 || from.indexOf('viabcp') !== -1) {
    return TEMPLATES.bcp(body, subject, date, messageId);
  }
  return null; // desconocido
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
var TEMPLATES = {

  // -------------------- YAPE --------------------
  // Correo solo para yapeos > S/10. Llega cuando pagas Y cuando te yapean.
  yape: function (body, subject, date, messageId) {
    var amountM = firstMatch(body, [
      /S\/\s*([\d.,]+)/i,
      /por\s+S\/\s*([\d.,]+)/i,
    ]);
    // Contraparte: "a Juan Perez" / "de Maria Lopez"
    var who = firstMatch(body, [
      /(?:a|para)\s+([A-ZÁÉÍÓÚÑ][\w .'-]{2,40})/,
      /(?:de|recibiste de)\s+([A-ZÁÉÍÓÚÑ][\w .'-]{2,40})/,
    ]);
    var voucher = firstMatch(body, [/(?:operaci[oó]n|n[uú]mero)\D*(\d{6,})/i]);
    var text = subject + ' ' + body;

    return {
      source: 'email_yape',
      channel: 'yape',
      // direction/status los infiere el endpoint del `text` (pagaste/te yapearon/etc.)
      occurred_at: toIsoLima(date),
      merchant: who ? who[1].trim() : 'Yape',
      counterparty: who ? who[1].trim() : null,
      amount: amountM ? parseAmount(amountM[1]) : 0,
      currency: 'PEN',
      external_ref: voucher ? 'yape:' + voucher[1] : 'gmail:' + messageId,
      text: text,
    };
  },

  // -------------------- PLIN (vía alerta del banco) --------------------
  plin: function (body, subject, date, messageId, from) {
    var amountM = firstMatch(body, [/S\/\s*([\d.,]+)/i, /US\$\s*([\d.,]+)/i]);
    var who = firstMatch(body, [
      /(?:a|para|de)\s+([A-ZÁÉÍÓÚÑ][\w .'-]{2,40})/,
    ]);
    var voucher = firstMatch(body, [/(?:operaci[oó]n|referencia)\D*(\d{6,})/i]);
    var text = subject + ' ' + body;
    var src = (from && from.indexOf('bcp') !== -1) ? 'email_bcp' : 'email_interbank';

    return {
      source: src,
      channel: 'plin',
      occurred_at: toIsoLima(date),
      merchant: who ? who[1].trim() : 'Plin',
      counterparty: who ? who[1].trim() : null,
      amount: amountM ? parseAmount(amountM[1]) : 0,
      currency: detectCurrency(body),
      external_ref: voucher ? 'plin:' + voucher[1] : 'gmail:' + messageId,
      text: text,
    };
  },

  // -------------------- INTERBANK (tarjeta / consumo) --------------------
  interbank: function (body, subject, date, messageId) {
    var amountM = firstMatch(body, [/S\/\s*([\d.,]+)/i, /US\$\s*([\d.,]+)/i]);
    // Comercio: suele venir como "en COMERCIO" / "Establecimiento: COMERCIO"
    var merch = firstMatch(body, [
      /(?:en|Establecimiento:?)\s+([A-Z0-9][\w &.'*\/-]{2,40})/,
    ]);
    var card = firstMatch(body, [/(?:tarjeta|terminada en)\D*(\d{4})\b/i]);
    var voucher = firstMatch(body, [/(?:operaci[oó]n|referencia)\D*(\d{6,})/i]);
    var text = subject + ' ' + body;

    return {
      source: 'email_interbank',
      channel: 'tarjeta',
      occurred_at: toIsoLima(date),
      merchant: merch ? merch[1].trim() : (subject || 'Interbank'),
      amount: amountM ? parseAmount(amountM[1]) : 0,
      currency: detectCurrency(body),
      card_label: card ? 'Interbank ****' + card[1] : 'Interbank',
      external_ref: voucher ? 'ibk:' + voucher[1] : 'gmail:' + messageId,
      text: text,
    };
  },

  // -------------------- BCP (tarjeta / consumo) --------------------
  bcp: function (body, subject, date, messageId) {
    var amountM = firstMatch(body, [/S\/\s*([\d.,]+)/i, /US\$\s*([\d.,]+)/i]);
    var merch = firstMatch(body, [
      /(?:en|Comercio:?|Establecimiento:?)\s+([A-Z0-9][\w &.'*\/-]{2,40})/,
    ]);
    var card = firstMatch(body, [/(?:tarjeta|terminada en)\D*(\d{4})\b/i]);
    var voucher = firstMatch(body, [/(?:operaci[oó]n|referencia)\D*(\d{6,})/i]);
    var text = subject + ' ' + body;

    return {
      source: 'email_bcp',
      channel: 'tarjeta',
      occurred_at: toIsoLima(date),
      merchant: merch ? merch[1].trim() : (subject || 'BCP'),
      amount: amountM ? parseAmount(amountM[1]) : 0,
      currency: detectCurrency(body),
      card_label: card ? 'BCP ****' + card[1] : 'BCP',
      external_ref: voucher ? 'bcp:' + voucher[1] : 'gmail:' + messageId,
      text: text,
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
