# Deployment and service configuration

## 1. Supabase project

Create a dedicated Supabase project and enable email/password authentication with email confirmation.
Configure the production site URL and allow only the intended web origin and these redirects:

- `https://YOUR_HOST/auth/callback`
- `https://YOUR_HOST/auth/callback?next=/onboarding`
- `https://YOUR_HOST/auth/callback?next=/account/password`
- `https://YOUR_HOST/auth/confirm`

Use a production SMTP provider for invitation, confirmation and recovery emails.
Configure email templates to point at the server OTP confirmation endpoint:

```text
Signup:
{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=signup

Invitation:
{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=invite

Recovery:
{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=recovery
```

PKCE code callbacks are also supported at /auth/callback. Never log token-bearing callback query strings.
Test invitation and recovery links on a different device/browser before launch; the token-hash templates support this.
Expired or reused links return to login.

## 2. Database migration

Review the SQL files in `supabase/migrations/`.
Apply it to the intended project with the Supabase migration workflow or an authenticated database migration runner.
On 25 September 2026 the clinical workflow, user profiles, and trigger-execution hardening migrations were applied to project `jesqomurskzlegtkzlgm` (Dr.Retina). Local filenames match the hosted migration versions. Do not reapply their SQL manually to this project. For another project, apply all migrations in order.

The migration creates private `retina` and `retina_private` schemas, enables and forces RLS, and creates
`retina_api` and `retina_worker` login roles without passwords.
Set strong, separate database credentials for those roles through your secure database administration process.
Use TLS (`sslmode=require`, or stricter verification) on remote database connections.
Do not use `postgres`, a table-owner role, or a BYPASSRLS role for the API/worker: startup rejects them.

The API role has no UPDATE/DELETE rights on images, AI outputs, quality results, doctor reviews or audit rows.
The worker may process jobs across organizations, but cannot manage users, modify patients or issue clinical reviews.
No anonymous or authenticated Supabase Data API role can access the application schemas.
Do not add the private schemas to Supabase's exposed-schema list.

Functions in `retina_private` are narrowly scoped SECURITY DEFINER lookups for active membership and
`auth.sessions` validation. Their search paths are fixed and their execution is denied to browser roles.
Run Supabase database/security advisors on the configured project after migration, then repeat the live two-tenant tests.

## 3. Image storage

The migration creates the `retinal-images` bucket as private with a 25 MB limit and JPEG/PNG MIME types.
If a bucket with this name already exists, verify it is private and has the expected restrictions before proceeding.
There must be no public/broad authenticated policy allowing direct reads or overwrites of its objects.

Original uploads use unique organization/screening/object identifiers, a SHA-256 digest, and no upsert.
Every read is authorized through the clinical API before bytes are returned. No public image URLs are emitted.
Retakes and explanation overlays use different objects; originals are never replaced.

Configure storage backups and a clinic-approved retention policy.
An object uploaded just before a database/network failure can remain unreferenced; preserve it for recovery and
reconcile such objects administratively. Do not run automatic original-image deletion.

## 4. Environment settings

Web (`.env.local` locally, deployment secrets in production):

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`
- `API_INTERNAL_BASE_URL` — private API address, ending in /api/v1
- `APP_URL` — exact browser origin, including HTTPS in production
- `API_REVALIDATE_SECRET` — optional existing revalidation endpoint

API (`backend/.env` locally):

- `DATABASE_URL` — retina_api connection; never the worker role
- `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY` — server only, for Auth invitations and private object storage
- `APP_URL`, `ENVIRONMENT=production`
- `AI_SERVICE_URL`, `AI_SERVICE_KEY`, `AI_MODEL_VERSION`

Worker: use the same service settings with its own `DATABASE_URL` for retina_worker.
Docker Compose reads `WORKER_DATABASE_URL` from its environment and overrides the backend env file for the worker.
The model URL must be HTTPS in production. Pin the approved model version.

## 5. Containers

`Dockerfile` builds the Next.js standalone server with Node 24.
`backend/Dockerfile` uses Python 3.13 and the frozen uv lockfile.
Both run as non-root users.

From the project directory, set the Compose interpolation variables securely
(`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`, `APP_URL`, `WORKER_DATABASE_URL`),
then run:

```text
docker compose build
docker compose up -d
```

The web service exposes port 3000. The API remains on the internal container network.
Put the web service behind an HTTPS reverse proxy. Cap uploads at 27 MB at the edge as well as in application code.
Apply appropriate request/connection rate limits; Supabase authentication limits alone do not limit image traffic.
Do not cache authenticated HTML, JSON, report pages, images or callback responses.
Do not expose database ports, the worker, /docs, or model credentials to the public network.

Health endpoints: API `/health/live` and `/health/ready`.
Readiness confirms database connectivity; it does not certify model availability or clinical suitability.
Use container restart policies and monitor failed/stale jobs, storage failures and queue age.
A crashed worker's expired lease is recoverable. Explicit model/service failures require a technician retry after resolution.

## 6. First organization

1. Open /onboarding and register the administrator's email.
2. Confirm the email, sign in, and enter organization details.
3. Create the organization; the backend grants ORG_ADMIN to that authenticated owner.
4. Invite doctors and technicians from User Management.
5. Invitees follow their email link, set their own password, and sign in.
6. Doctors set availability; technicians register synthetic test patients and submit test captures.
7. Verify and finalize one report, request an additional image on another, and complete a retake.

Admin-created users never receive or expose an application-generated plaintext password.
Changing roles or disabling users updates membership directly; old token metadata cannot preserve prior access.
The optional platform SUPER_ADMIN role is not implemented. Platform-level organization suspension is an operator database action.

## 7. Launch acceptance

Run the automated suites, then test with two real Supabase organizations and separate accounts.
Confirm invitations, confirmation, recovery, expiration, logout and revocation against actual Supabase.
Confirm neither organization can read the other's patient/report/image IDs or assign its doctors.
Verify original-image bytes, backup restoration, retry behavior, concurrent review conflicts, and worker recovery under your deployment's actual PostgreSQL concurrency.
Confirm the real model returns the documented quality/prediction/Grad-CAM++ contract and that a qualified clinical team has validated it for the intended screening workflow.

No hosted deployment, live-service email test, Docker image execution, backup restore, or clinical model validation was performed in this workspace.
