-- =============================================================================
-- Reglas nuevas a partir del estado de cuenta real de Interbank (may-ago 2026).
-- Cubre comercios que aparecían de verdad y no tenían regla → caían en
-- "Sin categoría". Idempotente.
-- =============================================================================

insert into public.category_rules (match_text, category, priority) values
  -- Comer fuera / restaurantes vistos en el estado de cuenta
  ('DANTE',              'Comer fuera', 15),
  ('FUKU',               'Comer fuera', 15),
  ('TANTA',              'Comer fuera', 15),
  ('EL HORNERO',         'Comer fuera', 15),
  ('QUINOA CAFE',        'Comer fuera', 15),
  ('ARUMA',              'Comer fuera', 12),
  ('DON MANUE',          'Comer fuera', 12),
  ('LUCHA',              'Comer fuera', 12),
  ('MC DONALD',          'Comer fuera', 15), -- 'MC DONALDS' no calzaba con la regla 'MCDONALD' (sin espacio)

  -- Antojos
  ('PICARONES',          'Antojos', 15),
  ('HELADERIA',          'Antojos', 12),
  ('LA FRUTA DEL SUR',   'Antojos', 12),

  -- Entretenimiento
  ('CINEPOLIS',          'Entretenimiento', 12),
  ('EVENTRID',           'Entretenimiento', 12),
  ('EVENTBRITE',         'Entretenimiento', 12),

  -- Transporte
  ('APPARKA',            'Transporte', 15),
  ('DLC RIDES',          'Transporte', 15),

  -- Salud
  ('MIFARMA',            'Salud', 15),
  ('SANNA',              'Salud', 15),

  -- Belleza
  ('IL SALONE',          'Belleza', 12),

  -- Tecnología
  ('SAMSUNGPERU',        'Tecnología', 15),
  ('SAMSUNG',            'Tecnología', 10),

  -- Suscripciones (¡tu propia suscripción de Claude/Anthropic!)
  ('ANTHROPIC',          'Suscripciones', 18),
  ('CLAUDE',             'Suscripciones', 15),

  -- Seguros (cargo obligatorio de la tarjeta)
  ('DESGRAVAMEN',        'Seguros', 18),

  -- Mercado/minimarket
  ('MARKET PALERMO',     'Mercado/minimarket', 12),

  -- Salidas (bares vía pasarela Openpay; comercio real no identificable)
  ('PERU BAR',           'Salidas', 10)
on conflict do nothing;
