# Supabase authentication — Dr.Retina

## Implemented and applied

Next.js 16 App Router uses the pinned official `@supabase/ssr` and `@supabase/supabase-js` libraries. FastAPI independently validates bearer tokens with Supabase and derives clinical permissions from private database membership, including live session checks. No password is stored in application tables and no editable metadata grants a role.

Local `.env.local` contains the supplied project URL and publishable key. It is ignored by version control. Never put a service-role key or database password in a `NEXT_PUBLIC_*` variable.

Project: `jesqomurskzlegtkzlgm`, Dr.Retina. Three migrations were applied on 25 September 2026:

- `20260925140031_clinical_workflow.sql`: private clinical schema, membership/RBAC, tenant RLS, private storage bucket and dedicated API/worker roles.
- `20260925140041_user_profiles.sql`: profile ID references `auth.users`; signup trigger and existing-user backfill. Authenticated users may select their own profile and update only their own `display_name`. No client insert/delete or ID changes are granted.
- `20260925140346_restrict_rls_trigger_execution.sql`: removes client execution privileges on the project's existing RLS event trigger function.

Profile names do not change clinical member identity or organization roles. Clinical role changes remain authorized admin operations through FastAPI.

## Required dashboard configuration

Open [Authentication settings](https://supabase.com/dashboard/project/jesqomurskzlegtkzlgm/auth/url-configuration).

1. For local development, set Site URL to `http://localhost:3000`. Add these exact redirect URLs:
   - `http://localhost:3000/auth/callback`
   - `http://localhost:3000/auth/callback?next=/onboarding`
   - `http://localhost:3000/auth/callback?next=/account/password`
   - `http://localhost:3000/auth/confirm`
2. For deployment, set Site URL and `APP_URL` to the HTTPS app origin, add equivalent production redirects, and set the two public Supabase variables before building.
3. Email signup is enabled and email confirmation is required (verified through the public Auth settings endpoint). Keep these settings. Google and other social sign-ins were not enabled.
4. Configure a custom SMTP provider. Supabase's default email service has delivery restrictions; test with an authorized recipient before inviting staff.
5. Use these email links in the Supabase templates so confirmation works across devices:

```text
Confirm signup: {{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=signup
Invite user: {{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=invite
Reset password: {{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=recovery
```

6. Configure the Auth password policy to at least 12 characters, password breach protection where available, and appropriate rate limits. The app validates 12–128 characters for new passwords. Set a suitable JWT lifetime for clinic use.
7. Do not log callback URLs, tokens, password form bodies, or sensitive headers at your reverse proxy/host.

## Clinical API configuration

The publishable key is sufficient for registration, login, verification, recovery and the `/account` profile page. It does not provide database administration or invitation privileges.

To open clinical portals or create an organization, configure `backend/.env` from its example with the `retina_api` database connection, Supabase URL/publishable key, and server-only service-role key. Set the database-role passwords securely; the migrations deliberately do not embed them. Start the API with `uv run python -m app`. Follow DEPLOYMENT.md for the worker and production setup.

If Supabase login succeeds but FastAPI is unavailable, the user lands on `/account` with an explicit notice; this does not grant clinical access. Role selection or profile edits never authorize access. Doctors and technicians are invited by an organization admin; self-registration creates only an Auth account until verified organization onboarding completes.

## Acceptance testing

Automated tests cover registration validation, login routing, unverified-email errors, global logout/failure handling, recovery, password updates, verification resending, profiles RLS, and unauthenticated/forged-cookie rejection. Hosted PostgreSQL profile tests passed and were rolled back; no test users remain. The hosted security advisor returned no findings after hardening.

Before launch, use an email address you control to complete these live checks:

1. Register through `/onboarding`, confirm the email, then open `/account` and save a profile name.
2. Sign out, sign in, reload the page and reopen the browser to confirm session persistence.
3. Request recovery via `/forgot-password`, open the email on another browser/device, set a new password, and sign in with it. The old password must fail.
4. Verify reused/expired links show a useful error, and anonymous requests to `/account`, `/account/password` and clinical portals redirect to login.
5. With the configured backend, complete organization onboarding, invite a doctor and technician, and verify cross-role and cross-organization access is rejected.

Email delivery and successful browser login with a real mailbox have not been tested; no test emails were sent. Signup links, SMTP and production redirect settings require the manual steps above.

Run `npm test`, `node tests/database/profiles.mjs`, `npm run test:db`, `npm run test:integration`, `npm run typecheck`, `npm run lint`, and `npm run build`. Browser checks use `npm run test:e2e` (set `PLAYWRIGHT_CHANNEL=msedge` on this Windows machine and `PLAYWRIGHT_EXTERNAL_SERVER=true` if the dev server is already running).

References: [Supabase SSR](https://supabase.com/docs/guides/auth/server-side/creating-a-client), [user profiles](https://supabase.com/docs/guides/auth/managing-user-data), [redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls).
