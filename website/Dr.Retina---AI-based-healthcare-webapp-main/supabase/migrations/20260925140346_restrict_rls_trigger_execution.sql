-- This project-provided event trigger must not be callable by Data API roles.
-- Revoking client execution does not disable the DDL event trigger.
do $$ begin
  if to_regprocedure('public.rls_auto_enable()') is not null then
    revoke execute on function public.rls_auto_enable() from public, anon, authenticated;
  end if;
end $$;
