-- 001_schema.sql — Anglés Marketingin liidikanta.
--
-- Ajetaan kerran Supabasen SQL-editorissa. Kaikki taulut ovat public-skeemassa,
-- koska PostgREST julkaisee vain sen — mutta jokaisessa on RLS päällä ilman
-- yhtäkään policya. Se on tarkoituksellista: RLS päällä ilman policya tarkoittaa
-- että anon- ja authenticated-avaimet eivät lue eivätkä kirjoita mitään.
-- Vain service-role-avain (joka ohittaa RLS:n) toimii, ja se elää ainoastaan
-- Vercelin ympäristömuuttujana. Vuotanut anon-avain antaa nolla pääsyä.
--
-- ÄLÄ lisää tänne julkista insert-policya lomaketta varten. Insertit tehdään
-- palvelimella app.py:ssä, ei selaimessa.

create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Yhteydenotot (yhteystiedot.html -> POST /api/contact)
-- GDPR-peruste: sopimusta edeltävä toimenpide. Säilytys 24 kk.
-- ---------------------------------------------------------------------------
create table if not exists public.contact_leads (
    id          uuid primary key default gen_random_uuid(),
    created_at  timestamptz not null default now(),
    nimi        text not null,
    email       text not null,
    ala         text,
    paketti     text,
    viesti      text,
    source      text,
    utm         jsonb,
    status      text not null default 'uusi'
                check (status in ('uusi', 'yhteydessä', 'tarjous',
                                  'asiakas', 'ei_kiinnosta')),
    notes       text,
    notified_at timestamptz,
    -- IP:tä ei tallenneta koskaan raakana: sha256(IP_HASH_SALT + ip).
    -- Antaa roskapostitriagen ilman että kerätään IP-osoitteita.
    ip_hash     text,
    user_agent  text
);

create index if not exists contact_leads_created_idx
    on public.contact_leads (created_at desc);
create index if not exists contact_leads_status_idx
    on public.contact_leads (status);

-- ---------------------------------------------------------------------------
-- Auditointiajot (POST /api/audit). Säilytys 90 pv.
-- ---------------------------------------------------------------------------
create table if not exists public.audit_runs (
    id            uuid primary key default gen_random_uuid(),
    created_at    timestamptz not null default now(),
    target_url    text not null,
    host          text,
    status        text not null default 'ok'
                  check (status in ('ok', 'fetch_error', 'error')),
    overall_score numeric,
    grade         text,
    issues_count  integer,
    duration_ms   integer,
    -- koko run_audit-dict sellaisenaan: pisteytys voi muuttua, ajon
    -- alkuperäinen tulos ei
    result        jsonb,
    ip_hash       text
);

create index if not exists audit_runs_created_idx
    on public.audit_runs (created_at desc);
create index if not exists audit_runs_host_idx
    on public.audit_runs (host);

-- ---------------------------------------------------------------------------
-- SEO-testin liidit (POST /api/lead).
-- GDPR-peruste: nimenomainen suostumus markkinointiin — siksi consent_text
-- talletetaan sellaisena kuin se näytettiin, ei viittauksena. Säilytys 24 kk.
-- ---------------------------------------------------------------------------
create table if not exists public.audit_leads (
    id                uuid primary key default gen_random_uuid(),
    created_at        timestamptz not null default now(),
    email             text not null,
    audit_run_id      uuid references public.audit_runs (id) on delete set null,
    score             numeric,
    grade             text,
    source            text,
    consent           boolean not null default false,
    consent_text      text,
    -- false = pisteet tulivat selaimesta, ei audit_runs-taulusta
    trusted           boolean not null default false,
    mailerlite_status text,
    ip_hash           text
);

create index if not exists audit_leads_created_idx
    on public.audit_leads (created_at desc);

-- ---------------------------------------------------------------------------
-- Rate limit -laskurit (rate_hit(), 003_rate_hit.sql)
-- ---------------------------------------------------------------------------
create table if not exists public.rate_limits (
    key          text primary key,
    window_start timestamptz not null default now(),
    count        integer not null default 0
);

create index if not exists rate_limits_window_idx
    on public.rate_limits (window_start);

-- ---------------------------------------------------------------------------
-- RLS päälle kaikkiin. Nolla policya — se on mekanismi, ei unohdus.
-- ---------------------------------------------------------------------------
alter table public.contact_leads enable row level security;
alter table public.audit_runs    enable row level security;
alter table public.audit_leads   enable row level security;
alter table public.rate_limits   enable row level security;

-- Pakota RLS myös taulun omistajalle, jottei omistajan oikeuksilla ajettu
-- kysely pääse ohi vahingossa.
alter table public.contact_leads force row level security;
alter table public.audit_leads   force row level security;

-- ---------------------------------------------------------------------------
-- leads_all — yksi aikajana Kimille. Admin lukee vain tätä.
--
-- security_invoker = on on pakollinen: ilman sitä näkymä ajaisi omistajan
-- oikeuksilla ja anon-avain näkisi liidit RLS:n ohi. Vaatii Postgres 15+.
-- ---------------------------------------------------------------------------
create or replace view public.leads_all
with (security_invoker = on) as
    select 'contact'::text          as tyyppi,
           c.id,
           c.created_at,
           c.nimi,
           c.email,
           c.ala,
           c.paketti,
           c.viesti,
           c.source,
           c.status,
           null::numeric            as score,
           null::text               as grade,
           null::boolean            as consent
      from public.contact_leads c
    union all
    select 'audit'::text            as tyyppi,
           l.id,
           l.created_at,
           null::text               as nimi,
           l.email,
           null::text               as ala,
           null::text               as paketti,
           r.target_url             as viesti,
           l.source,
           l.mailerlite_status      as status,
           l.score,
           l.grade,
           l.consent
      from public.audit_leads l
      left join public.audit_runs r on r.id = l.audit_run_id;

-- Varmistus vyön päälle: näkymään ei tarvita pääsyä muilta kuin service-rolelta.
revoke all on public.leads_all from anon, authenticated;
