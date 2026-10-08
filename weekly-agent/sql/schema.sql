-- סוכן שבועי tehilauto.com: הרצה ידנית ב-Supabase (SQL Editor)
create table if not exists public.weekly_raw (
  id bigint generated always as identity primary key,
  week_start date not null,
  week_end date not null,
  source text not null check (source in ('gsc', 'ga4_traffic', 'ga4_engagement', 'ga4_video', 'ga4_leads')),
  payload jsonb not null,
  created_at timestamptz not null default now(),
  unique (week_start, source)
);

-- RLS מופעל וללא policies: גישה רק דרך מפתח service_role של הסוכן.
alter table public.weekly_raw enable row level security;
