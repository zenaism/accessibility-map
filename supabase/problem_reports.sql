-- "Report a problem" for the Accessibility Map: a visitor describes a problem and can attach one photo.
--
-- Run once in the Supabase SQL editor (Dashboard -> SQL -> New query -> paste -> Run).
-- Safe to re-run: every statement is idempotent.
-- The map shows the "Report a problem" button only after this script has been run (it checks report_ping()).
--
-- Design (same pattern as ratings.sql)
--   * problem_reports        raw rows. NOT readable or writable from the browser.
--   * submit_problem_report  the only way the public page can write: validates everything, rate-limits per device,
--                            ignores robots (hidden field), and is safe to retry (same report id = same row).
--   * problem_reports_review a view for the accessibility team in the Supabase dashboard (no photo bytes, so it is fast).
--   * report_ping()          lets the page check that this script has been run before it shows the button.
-- The photo is resized and stripped of location data in the visitor's browser, then stored in the row (JPEG, at most
-- 400 KB). The team views photos with scripts/export_reports.py (see docs/problem_reports.md).
-- No name, account or IP address is stored. The contact field is optional and only for follow-up questions.

create table if not exists public.problem_reports (
  id          uuid primary key,                                  -- chosen by the browser: a retry cannot create a duplicate
  created_at  timestamptz not null default now(),
  link_id     text check (link_id is null or link_id ~ '^[a-z0-9-]{1,140}$'),   -- the map's place id; null = about the map itself
  place_name  text check (char_length(place_name) <= 200),
  region      text check (region is null or region ~ '^[a-z0-9_]{1,40}$'),
  category    text not null check (category in
                ('blocked_or_broken', 'wrong_info', 'less_accessible', 'missing_info', 'other')),
  description text not null check (char_length(description) between 5 and 1000),
  contact     text check (char_length(contact) <= 200),
  photo       bytea check (photo is null or (octet_length(photo) <= 400000
                and substring(photo from 1 for 3) = '\xffd8ff'::bytea)),   -- a JPEG, at most 400 KB
  device_id   uuid not null,                                     -- random id kept in the visitor's browser, for rate limits
  page_url    text check (char_length(page_url) <= 300),
  user_agent  text check (char_length(user_agent) <= 300),
  -- the accessibility team's side: edit these in the dashboard
  status      text not null default 'new'
                check (status in ('new', 'in_review', 'needs_info', 'fixed', 'wont_fix', 'duplicate')),
  team_notes  text,
  updated_at  timestamptz not null default now()
);
create index if not exists problem_reports_created_idx on public.problem_reports (created_at desc);
create index if not exists problem_reports_place_idx on public.problem_reports (link_id);
create index if not exists problem_reports_device_idx on public.problem_reports (device_id, created_at);

alter table public.problem_reports enable row level security;
revoke all on public.problem_reports from anon, authenticated;

create or replace function public.submit_problem_report(
  p_report_id uuid, p_device_id uuid, p_category text, p_description text,
  p_link_id text default null, p_place_name text default null, p_region text default null,
  p_contact text default null, p_photo_b64 text default null,
  p_page_url text default null, p_user_agent text default null,
  p_website text default null                                    -- hidden "honeypot" field: real people leave it empty
) returns text
language plpgsql security definer set search_path = public as $$
declare
  v_photo bytea := null;
begin
  if coalesce(p_website, '') <> '' then
    return upper(substr(p_report_id::text, 1, 8));               -- looks like a robot: pretend it worked, store nothing
  end if;
  if (select count(*) from problem_reports
        where device_id = p_device_id and created_at > now() - interval '1 day') >= 10 then
    raise exception 'Too many reports from this device today; please try again tomorrow.';
  end if;
  if p_photo_b64 is not null and p_photo_b64 <> '' then
    if char_length(p_photo_b64) > 560000 then
      raise exception 'The photo is too large.';
    end if;
    v_photo := decode(p_photo_b64, 'base64');
    if octet_length(v_photo) > 400000 or substring(v_photo from 1 for 3) <> '\xffd8ff'::bytea then
      raise exception 'The photo must be a JPEG of at most 400 KB.';
    end if;
  end if;
  insert into problem_reports (id, link_id, place_name, region, category, description, contact,
                               photo, device_id, page_url, user_agent)
  values (p_report_id, nullif(trim(p_link_id), ''), nullif(trim(p_place_name), ''), nullif(trim(p_region), ''),
          p_category, trim(p_description), nullif(trim(p_contact), ''), v_photo, p_device_id,
          left(p_page_url, 300), left(p_user_agent, 300))
  on conflict (id) do nothing;                                   -- a retry of the same report is not stored twice
  return upper(substr(p_report_id::text, 1, 8));                 -- the reference code shown to the visitor
end $$;
revoke all on function public.submit_problem_report from public;
grant execute on function public.submit_problem_report to anon, authenticated;

-- Delete my report: the browser that sent it knows both ids, nobody else does (the visitor sees only the short code).
create or replace function public.delete_problem_report(p_report_id uuid, p_device_id uuid) returns boolean
language plpgsql security definer set search_path = public as $$
declare n int;
begin
  delete from problem_reports where id = p_report_id and device_id = p_device_id;
  get diagnostics n = row_count;
  return n > 0;
end $$;
revoke all on function public.delete_problem_report from public;
grant execute on function public.delete_problem_report to anon, authenticated;

-- Retention: reports are kept for 24 months. Run now and then (SQL editor), or schedule it with pg_cron.
create or replace function public.purge_old_reports(p_months int default 24) returns int
language plpgsql security definer set search_path = public as $$
declare n int;
begin
  delete from problem_reports where created_at < now() - make_interval(months => p_months);
  get diagnostics n = row_count;
  return n;
end $$;
revoke all on function public.purge_old_reports from public, anon, authenticated;

-- The page asks this before showing the button, so nobody sees a form that cannot save.
create or replace function public.report_ping() returns text
language sql stable as $$ select 'ok'::text $$;
revoke all on function public.report_ping from public;
grant execute on function public.report_ping to anon, authenticated;

-- For the accessibility team (Dashboard -> Table Editor -> problem_reports_review). Photos are not in this view.
create or replace view public.problem_reports_review as
select
  upper(substr(id::text, 1, 8)) as ref,
  created_at, status, category, place_name, link_id, region, description, contact,
  (photo is not null) as has_photo, coalesce(octet_length(photo), 0) as photo_bytes,
  team_notes, page_url, id
from public.problem_reports
order by created_at desc;
revoke all on public.problem_reports_review from anon, authenticated;
