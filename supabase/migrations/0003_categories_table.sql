-- =============================================================================
-- Tabla `categories` — hace las categorías dinámicas (agregables desde el
-- dashboard) en vez de una lista fija en el código.
-- =============================================================================

create table if not exists public.categories (
  name          text primary key,
  expense_group text not null check (expense_group in
                  ('Fijo','Necesario','Bienestar','Lifestyle','Compras','Inversión','Otros')),
  created_at    timestamptz not null default now()
);

alter table public.categories enable row level security;
drop policy if exists categories_authenticated_all on public.categories;
create policy categories_authenticated_all on public.categories
  for all to authenticated using (true) with check (true);

insert into public.categories (name, expense_group) values
  ('Vivienda/Casa','Fijo'), ('Servicios','Fijo'), ('Impuestos','Fijo'), ('Suscripciones','Fijo'),
  ('Mercado/minimarket','Necesario'), ('Transporte','Necesario'), ('Combustible','Necesario'),
  ('Luna','Necesario'), ('Salud','Necesario'),
  ('Deporte','Bienestar'),
  ('Comer fuera','Lifestyle'), ('Delivery','Lifestyle'), ('Antojos','Lifestyle'),
  ('Salidas','Lifestyle'), ('Entretenimiento','Lifestyle'), ('Viajes','Lifestyle'),
  ('Compras personales','Compras'), ('Hogar','Compras'),
  ('Educación y Desarrollo','Inversión'),
  ('Otros','Otros'), ('Sin categoría','Otros'),
  -- Nuevas, más específicas (pedidas + sugeridas para desglosar mejor "Salidas"):
  ('Belleza','Bienestar'),
  ('Regalos','Lifestyle'),
  ('Salida familiar','Lifestyle'),
  ('Salida con pareja','Lifestyle'),
  ('Salida con amigos','Lifestyle'),
  ('Tecnología','Compras')
on conflict (name) do nothing;
