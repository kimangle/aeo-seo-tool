-- 002_retention.sql — säilytysajat.
--
-- tietosuoja.html lupaa jo että yhteydenotot poistetaan 24 kk kuluttua.
-- Lupaus on ollut olemassa, toteutus ei. Tämä on toteutus.
--
-- Auditoinnit 90 pv, liidit 24 kk, rate limit -laskurit 2 vrk (ne ovat
-- pelkkiä laskureita, pisin ikkuna on 24 h).
--
-- Ajastus on valinnainen. Tällä volyymilla käsin neljännesvuosittain riittää:
--     select public.purge_old_data();
-- pg_cron-versio on alla kommentoituna.

create or replace function public.purge_old_data()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    v_runs    integer;
    v_leads   integer;
    v_contact integer;
    v_rate    integer;
begin
    delete from public.audit_runs
     where created_at < now() - interval '90 days';
    get diagnostics v_runs = row_count;

    delete from public.audit_leads
     where created_at < now() - interval '24 months';
    get diagnostics v_leads = row_count;

    delete from public.contact_leads
     where created_at < now() - interval '24 months';
    get diagnostics v_contact = row_count;

    delete from public.rate_limits
     where window_start < now() - interval '2 days';
    get diagnostics v_rate = row_count;

    return jsonb_build_object(
        'audit_runs',    v_runs,
        'audit_leads',   v_leads,
        'contact_leads', v_contact,
        'rate_limits',   v_rate
    );
end;
$$;

revoke all on function public.purge_old_data() from public, anon, authenticated;

-- Valinnainen ajastus (vaatii pg_cron-laajennuksen Supabasen Database-osiosta):
--
-- create extension if not exists pg_cron;
-- select cron.schedule('purge-old-data', '15 3 * * *',
--                      $$select public.purge_old_data();$$);
