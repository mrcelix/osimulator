-- ============================================================================
--  osimulator · Supabase setup
--  Run this whole file in your Supabase project → SQL Editor → New query → Run.
--  It is safe to run more than once (idempotent).
--
--  After running:
--   1) Add yourself as an admin (replace the email):
--        insert into public.admins(email) values ('you@example.com')
--        on conflict do nothing;
--   2) Auth → Providers → enable Email, and (optional) Google.
--   3) Auth → URL Configuration → add your Site URL + redirect URLs
--        (e.g. https://osimulator.com , and http://localhost:* for testing).
--   4) Paste your Project URL + anon (public) key into osimulator
--        (Admin panel → Backend), or bake them into index.html.
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Helper: is the current signed-in user an admin?
-- (defined early so policies below can use it)
-- ----------------------------------------------------------------------------
create table if not exists public.admins (
  email text primary key
);
alter table public.admins enable row level security;
-- no public policies on admins → only service role / SQL editor can read it,
-- but is_admin() runs as SECURITY DEFINER so it can still check membership.

create or replace function public.is_admin()
returns boolean
language sql stable security definer set search_path = public as $$
  select exists (
    select 1 from public.admins a
    where lower(a.email) = lower(coalesce(auth.jwt() ->> 'email', ''))
  );
$$;

-- ----------------------------------------------------------------------------
-- profiles: one row per authenticated user (mirrors auth.users)
-- ----------------------------------------------------------------------------
create table if not exists public.profiles (
  id         uuid primary key references auth.users(id) on delete cascade,
  email      text,
  name       text,
  provider   text,
  created_at timestamptz default now()
);
alter table public.profiles enable row level security;

drop policy if exists "profiles self read"   on public.profiles;
drop policy if exists "profiles admin read"   on public.profiles;
drop policy if exists "profiles self upsert"  on public.profiles;
drop policy if exists "profiles self update"  on public.profiles;

create policy "profiles self read"  on public.profiles for select
  using (auth.uid() = id or public.is_admin());
create policy "profiles self upsert" on public.profiles for insert
  with check (auth.uid() = id);
create policy "profiles self update" on public.profiles for update
  using (auth.uid() = id);

-- auto-create a profile row when someone signs up
create or replace function public.handle_new_user()
returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email, name, provider)
  values (
    new.id,
    new.email,
    coalesce(new.raw_user_meta_data ->> 'name',
             new.raw_user_meta_data ->> 'full_name',
             split_part(new.email, '@', 1)),
    coalesce(new.raw_app_meta_data ->> 'provider', 'email')
  )
  on conflict (id) do nothing;
  return new;
end; $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ----------------------------------------------------------------------------
-- events: analytics (page views + OS launches + clicks). Anyone may insert.
-- Only admins may read them back (aggregates shown in the admin panel).
-- ----------------------------------------------------------------------------
create table if not exists public.events (
  id    bigint generated always as identity primary key,
  type  text not null,
  label text,
  ts    timestamptz default now()
);
alter table public.events enable row level security;
create index if not exists events_ts_idx   on public.events (ts);
create index if not exists events_type_idx  on public.events (type);

drop policy if exists "events insert" on public.events;
drop policy if exists "events admin read" on public.events;
create policy "events insert"     on public.events for insert
  to anon, authenticated with check (true);
create policy "events admin read" on public.events for select
  using (public.is_admin());

-- ----------------------------------------------------------------------------
-- newsletter: email subscribers. Anyone may subscribe; admins may read.
-- ----------------------------------------------------------------------------
create table if not exists public.newsletter (
  email text primary key,
  ts    timestamptz default now()
);
alter table public.newsletter enable row level security;

drop policy if exists "nl insert" on public.newsletter;
drop policy if exists "nl admin read" on public.newsletter;
create policy "nl insert"     on public.newsletter for insert
  to anon, authenticated with check (true);
create policy "nl admin read" on public.newsletter for select
  using (public.is_admin());

-- ----------------------------------------------------------------------------
-- guides: shared "Record & Play" walkthroughs. Public read; owner writes.
-- ----------------------------------------------------------------------------
create table if not exists public.guides (
  id          text primary key,
  title       text,
  data        jsonb not null,
  owner       uuid references auth.users(id) on delete set null,
  owner_email text,
  owner_name  text,
  created_at  timestamptz default now()
);
alter table public.guides enable row level security;
create index if not exists guides_owner_idx   on public.guides (owner);
create index if not exists guides_created_idx  on public.guides (created_at);

drop policy if exists "guides public read" on public.guides;
drop policy if exists "guides owner insert" on public.guides;
drop policy if exists "guides owner delete" on public.guides;
create policy "guides public read"  on public.guides for select using (true);
create policy "guides owner insert"  on public.guides for insert
  to authenticated with check (auth.uid() = owner);
create policy "guides owner delete"  on public.guides for delete
  using (auth.uid() = owner or public.is_admin());

-- ----------------------------------------------------------------------------
-- site_config: single row of admin-managed site settings that every visitor
-- reads on load (header menu, feature flags, per-OS enable/disable).
-- ----------------------------------------------------------------------------
create table if not exists public.site_config (
  id           int primary key default 1,
  nav_menu     jsonb,
  features     jsonb,
  os_overrides jsonb,
  os_menus     jsonb,
  updated_at   timestamptz default now(),
  constraint site_config_single_row check (id = 1)
);
-- If you created site_config before os_menus existed, add the column:
alter table public.site_config add column if not exists os_menus jsonb;
alter table public.site_config enable row level security;

drop policy if exists "config public read" on public.site_config;
drop policy if exists "config admin insert" on public.site_config;
drop policy if exists "config admin update" on public.site_config;
create policy "config public read"  on public.site_config for select using (true);
create policy "config admin insert" on public.site_config for insert
  to authenticated with check (public.is_admin());
create policy "config admin update" on public.site_config for update
  using (public.is_admin());

insert into public.site_config (id) values (1) on conflict do nothing;

-- ============================================================================
--  Done. Remember step 1 above: add your admin email to public.admins.
-- ============================================================================
