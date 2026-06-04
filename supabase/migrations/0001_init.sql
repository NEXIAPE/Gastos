-- =============================================================================
-- Gastos — esquema inicial
-- Tablas: transactions, category_rules, budgets (fase 2), insights, settings
-- Zona horaria de referencia: America/Lima (UTC-5, sin DST)
-- =============================================================================

create extension if not exists "pgcrypto";

-- -----------------------------------------------------------------------------
-- transactions
-- -----------------------------------------------------------------------------
create table if not exists public.transactions (
  id              uuid primary key default gen_random_uuid(),
  occurred_at     timestamptz not null default now(),
  merchant_raw    text,
  merchant_clean  text,
  amount          numeric(14,2) not null check (amount >= 0),
  direction       text not null default 'out'
                    check (direction in ('out','in','transfer')),
  status          text not null default 'confirmed'
                    check (status in ('confirmed','declined','reversed','refunded','pending','needs_review')),
  refund_of       uuid references public.transactions(id) on delete set null,
  is_recurring    boolean not null default false,
  counterparty    text,
  currency        text not null default 'PEN' check (currency in ('PEN','USD')),
  fx_rate         numeric(12,4),
  amount_pen      numeric(14,2),
  category        text not null default 'Sin categoría',
  card_label      text,
  source          text not null default 'manual'
                    check (source in ('apple_pay_shortcut','email_yape','email_plin',
                                      'email_interbank','email_bcp','manual','import')),
  channel         text check (channel in ('apple_pay','yape','plin','tarjeta','efectivo')),
  notes           text,
  tags            text[] not null default '{}',
  external_ref    text,
  raw_payload     jsonb,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now()
);

-- external_ref es la clave de idempotencia/deduplicación principal.
-- Único cuando está presente (varios NULL permitidos).
create unique index if not exists transactions_external_ref_uniq
  on public.transactions (external_ref)
  where external_ref is not null;

create index if not exists transactions_occurred_at_idx on public.transactions (occurred_at desc);
create index if not exists transactions_category_idx    on public.transactions (category);
create index if not exists transactions_channel_idx     on public.transactions (channel);
create index if not exists transactions_direction_idx   on public.transactions (direction);
create index if not exists transactions_status_idx      on public.transactions (status);
create index if not exists transactions_merchant_idx    on public.transactions (merchant_clean);
-- Índice para el fallback de dedup (monto+moneda+comercio en una ventana de tiempo).
create index if not exists transactions_dedup_idx
  on public.transactions (amount, currency, merchant_clean, occurred_at);

-- -----------------------------------------------------------------------------
-- category_rules — categorización por texto de comercio
-- -----------------------------------------------------------------------------
create table if not exists public.category_rules (
  id          uuid primary key default gen_random_uuid(),
  match_text  text not null,
  category    text not null,
  priority    int  not null default 0,
  created_at  timestamptz not null default now()
);
create index if not exists category_rules_priority_idx on public.category_rules (priority desc);

-- -----------------------------------------------------------------------------
-- budgets — estructura lista para FASE 2 (sin activar límites ni alertas)
-- -----------------------------------------------------------------------------
create table if not exists public.budgets (
  id          uuid primary key default gen_random_uuid(),
  category    text not null unique,
  amount_pen  numeric(14,2) not null,
  period      text not null default 'monthly' check (period in ('monthly')),
  active      boolean not null default false,
  created_at  timestamptz not null default now()
);

-- -----------------------------------------------------------------------------
-- insights — recomendaciones semanales generadas por IA
-- -----------------------------------------------------------------------------
create table if not exists public.insights (
  id          uuid primary key default gen_random_uuid(),
  week        date not null,                 -- lunes (inicio) de la semana, en America/Lima
  content     text not null,                 -- markdown con las recomendaciones
  summary     jsonb,                         -- resumen numérico enviado a la IA (auditoría)
  model       text,                          -- modelo usado
  created_at  timestamptz not null default now()
);
create index if not exists insights_week_idx on public.insights (week desc);

-- -----------------------------------------------------------------------------
-- settings — configuración key/value (ej. tipo de cambio fijo)
-- -----------------------------------------------------------------------------
create table if not exists public.settings (
  key         text primary key,
  value       jsonb not null,
  updated_at  timestamptz not null default now()
);

insert into public.settings (key, value) values
  ('fx_usd_pen', '3.75'::jsonb)
on conflict (key) do nothing;

-- -----------------------------------------------------------------------------
-- updated_at automático
-- -----------------------------------------------------------------------------
create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end; $$;

drop trigger if exists trg_transactions_updated_at on public.transactions;
create trigger trg_transactions_updated_at
  before update on public.transactions
  for each row execute function public.set_updated_at();

-- -----------------------------------------------------------------------------
-- Row Level Security
-- App de un solo usuario: cualquier usuario autenticado (solo el dueño tiene
-- cuenta) puede leer/escribir. El service_role (Edge Functions) ignora RLS.
-- -----------------------------------------------------------------------------
alter table public.transactions  enable row level security;
alter table public.category_rules enable row level security;
alter table public.budgets        enable row level security;
alter table public.insights       enable row level security;
alter table public.settings       enable row level security;

do $$
declare t text;
begin
  foreach t in array array['transactions','category_rules','budgets','insights','settings']
  loop
    execute format('drop policy if exists %I_authenticated_all on public.%I;', t, t);
    execute format(
      'create policy %I_authenticated_all on public.%I
         for all to authenticated using (true) with check (true);', t, t);
  end loop;
end $$;

-- -----------------------------------------------------------------------------
-- Reglas semilla de categorización (de la data real + comercios comunes en Perú)
-- Mayor priority gana cuando varias reglas coinciden.
-- -----------------------------------------------------------------------------
insert into public.category_rules (match_text, category, priority) values
  ('MAKRO',            'Luna',               50),
  ('MORA',             'Vivienda/Casa',      30),
  ('MMA STORE',        'Deporte',            30),
  ('UBER',             'Transporte',         20),
  ('CABIFY',           'Transporte',         20),
  ('RIDE TAXI',        'Transporte',         20),
  ('BEAT',             'Transporte',         20),
  ('DIDI',             'Transporte',         20),
  ('ESTACION',         'Combustible',        20),
  ('SHELL',            'Combustible',        20),
  ('GRIFO',            'Combustible',        20),
  ('PRIMAX',           'Combustible',        20),
  ('REPSOL',           'Combustible',        20),
  ('PETROPERU',        'Combustible',        20),
  ('RAPPI',            'Delivery',           20),
  ('PEDIDOSYA',        'Delivery',           20),
  ('PEDIDOS YA',       'Delivery',           20),
  ('PUKU PUKU',        'Comer fuera',        15),
  ('JUAN VALDEZ',      'Comer fuera',        15),
  ('STARBUCKS',        'Comer fuera',        15),
  ('MARIA ALMENARA',   'Comer fuera',        15),
  ('7 SOPAS',          'Comer fuera',        15),
  ('LA CONDESA',       'Comer fuera',        15),
  ('MORELIA',          'Comer fuera',        15),
  ('PICKADELI',        'Comer fuera',        15),
  ('PERU MASTER FOOD', 'Comer fuera',        15),
  ('BEMBOS',           'Comer fuera',        15),
  ('KFC',              'Comer fuera',        15),
  ('HELADO DE LIMA',   'Antojos',            15),
  ('VENDOMATICA',      'Antojos',            15),
  ('TOTTUS',           'Mercado/minimarket', 10),
  ('PLAZA VEA',        'Mercado/minimarket', 10),
  ('WONG',             'Mercado/minimarket', 10),
  ('METRO',            'Mercado/minimarket', 10),
  ('MASS',             'Mercado/minimarket', 10),
  ('TU MARKA',         'Mercado/minimarket', 10),
  ('LISTO',            'Mercado/minimarket', 10),
  ('SELECTOS TAMAYO',  'Mercado/minimarket', 10),
  ('OXXO',             'Mercado/minimarket', 10),
  ('TAMBO',            'Mercado/minimarket', 10),
  ('FALABELLA',        'Compras/tiendas',    10),
  ('SAGA',             'Compras/tiendas',    10),
  ('RIPLEY',           'Compras/tiendas',    10),
  ('LUZ DEL SUR',      'Servicios',          10),
  ('ENEL',             'Servicios',          10),
  ('SEDAPAL',          'Servicios',          10),
  ('CLARO',            'Servicios',          10),
  ('MOVISTAR',         'Servicios',          10),
  ('ENTEL',            'Servicios',          10),
  ('SUNAT',            'Impuestos',          20),
  ('IMPUESTOS',        'Impuestos',          20),
  ('CINEPLANET',       'Entretenimiento',    10),
  ('CINEMARK',         'Entretenimiento',    10),
  ('NETFLIX',          'Suscripciones',      20),
  ('SPOTIFY',          'Suscripciones',      20),
  ('DISNEY',           'Suscripciones',      20),
  ('YOUTUBE',          'Suscripciones',      20),
  ('HBO',              'Suscripciones',      20),
  ('APPLE.COM',        'Suscripciones',      15),
  ('GOOGLE',           'Suscripciones',      10)
on conflict do nothing;
