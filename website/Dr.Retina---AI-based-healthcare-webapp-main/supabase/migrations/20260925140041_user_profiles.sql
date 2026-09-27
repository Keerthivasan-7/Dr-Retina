-- Profile data is never used for role or organization authorization.
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default '' check (char_length(display_name) <= 100),
  created_at timestamptz not null default now()
);
alter table public.profiles enable row level security;
alter table public.profiles force row level security;
revoke all on public.profiles from public, anon, authenticated;
grant select on public.profiles to authenticated;
grant update (display_name) on public.profiles to authenticated;
create policy profiles_read_own on public.profiles for select to authenticated
  using ((select auth.uid()) = id);
create policy profiles_update_own on public.profiles for update to authenticated
  using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

create schema if not exists auth_private;
revoke all on schema auth_private from public, anon, authenticated;
-- Auth-trigger execution only. No metadata is copied or interpreted as permissions.
create function auth_private.create_user_profile() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles(id) values (new.id);
  return new;
end;
$$;
revoke all on function auth_private.create_user_profile() from public, anon, authenticated;
create trigger create_user_profile after insert on auth.users
for each row execute function auth_private.create_user_profile();
insert into public.profiles(id) select id from auth.users on conflict (id) do nothing;
