-- 003_rate_hit.sql — rate limit yhtenä atomisena kutsuna.
--
-- Miksi kannassa eikä muistissa: Vercelin Python on tilaton. Joka
-- kylmäkäynnistys on uusi instanssi ja rinnakkaisia instansseja on monta,
-- joten muistissa oleva laskuri ei rajoita mitään — se antaa vain väärän
-- turvallisuudentunteen. /tmp pyyhkiytyy samasta syystä.
--
-- Funktio ottaa vastaan kaikki saman pyynnön rajat kerralla (esim. IP/10 min,
-- IP/24 h ja globaali/24 h), jotta HTTPS-kierroksia on yksi eikä kolme.
-- Ikkunan vanheneminen hoidetaan samassa UPSERTissa: jos ikkuna on umpeutunut,
-- laskuri nollataan ja ikkuna alkaa alusta.
--
-- Palauttaa: {"allowed": bool, "retry_after": int, "key": text|null}
--   retry_after = sekunteja siihen kun tiukin ylittynyt ikkuna vapautuu.

create or replace function public.rate_hit(
    p_keys    text[],
    p_limits  int[],
    p_windows int[]
)
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    i         int;
    n         int;
    v_count   int;
    v_start   timestamptz;
    v_allowed boolean := true;
    v_retry   int := 0;
    v_key     text := null;
begin
    n := coalesce(array_length(p_keys, 1), 0);
    if n = 0 then
        return jsonb_build_object('allowed', true, 'retry_after', 0, 'key', null);
    end if;
    if coalesce(array_length(p_limits, 1), 0) <> n
       or coalesce(array_length(p_windows, 1), 0) <> n then
        raise exception 'rate_hit: taulukoiden pituudet eivät täsmää';
    end if;

    for i in 1 .. n loop
        -- Yksi lause = atominen. Kaksi rinnakkaista pyyntöä ei voi lukea
        -- samaa laskuria ja kirjoittaa sen päälle, koska ON CONFLICT lukitsee
        -- rivin ja toinen pyyntö näkee ensimmäisen tuloksen.
        insert into public.rate_limits as r (key, window_start, count)
        values (p_keys[i], now(), 1)
        on conflict (key) do update
            set window_start = case
                    when r.window_start + make_interval(secs => p_windows[i]) <= now()
                    then now()
                    else r.window_start
                end,
                count = case
                    when r.window_start + make_interval(secs => p_windows[i]) <= now()
                    then 1
                    else r.count + 1
                end
        returning r.count, r.window_start into v_count, v_start;

        if v_count > p_limits[i] then
            v_allowed := false;
            if v_key is null then
                v_key := p_keys[i];
            end if;
            v_retry := greatest(v_retry, ceil(extract(epoch from
                (v_start + make_interval(secs => p_windows[i]) - now())))::int);
        end if;
    end loop;

    return jsonb_build_object('allowed', v_allowed,
                              'retry_after', greatest(v_retry, 0),
                              'key', v_key);
end;
$$;

-- Vain service-role kutsuu tätä. Selain ei puhu Supabaselle koskaan.
revoke all on function public.rate_hit(text[], int[], int[])
    from public, anon, authenticated;
