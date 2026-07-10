-- =============================================================================
-- Más categorías específicas (a criterio, complementan las pedidas en 0003).
-- Idempotente: puedes correrlo varias veces sin duplicar.
-- =============================================================================

insert into public.categories (name, expense_group) values
  ('Cumpleaños', 'Lifestyle'),
  ('Trámites', 'Necesario'),
  ('Seguros', 'Fijo'),
  ('Mantenimiento del hogar', 'Necesario'),
  ('Trabajo/Oficina', 'Necesario'),
  ('Imprevistos', 'Otros')
on conflict (name) do nothing;
