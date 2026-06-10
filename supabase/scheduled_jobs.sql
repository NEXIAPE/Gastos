-- =============================================================================
-- Jobs programados (pg_cron + pg_net) — EJECUTAR EN EL SQL EDITOR DE SUPABASE
-- Reemplaza <PROJECT_REF> y <SERVICE_ROLE_KEY> antes de correrlo.
-- Requiere las extensiones pg_cron y pg_net (Database → Extensions).
-- =============================================================================

create extension if not exists pg_cron;
create extension if not exists pg_net;

-- Recomendaciones semanales: cada lunes 08:00 hora Lima (= 13:00 UTC).
select cron.schedule(
  'weekly-insights',
  '0 13 * * 1',
  $$
  select net.http_post(
    url     := 'https://<PROJECT_REF>.supabase.co/functions/v1/weekly-insights',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'Authorization', 'Bearer <SERVICE_ROLE_KEY>'
    ),
    body    := '{}'::jsonb
  );
  $$
);

-- Para ver / borrar jobs:
--   select * from cron.job;
--   select cron.unschedule('weekly-insights');
