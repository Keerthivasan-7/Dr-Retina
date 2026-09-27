# Dr.Retina — SIH26038

Explainable diabetic-retinopathy screening workflow with three portals: lab technician, doctor, and organization administrator. The existing Next.js blue UI is retained and connected to a FastAPI backend.

## Implemented

- Supabase password authentication, verified-email onboarding, invitation/recovery flows, password changes and global logout.
- Backend-derived organization membership and role; legacy base64 cookies are ignored.
- PostgreSQL row-level security, live session checks, separate least-privilege API/worker roles, and tenant-safe foreign keys.
- Patient registration, private original-image preservation, upload validation, durable jobs, quality gating and model-service integration.
- Same-organization doctor assignment, availability, queues, reassignment and notifications.
- Separate immutable AI results and doctor assessments; verified reports, additional-analysis requests, linked retakes, patient history and printable final reports.
- Admin invitations, activation/revocation, role changes, password-reset emails, organization settings and aggregate activity.
- Docker deployment files, locked dependencies, unit tests, PostgreSQL isolation checks and a synthetic full-workflow integration test.

## Required external configuration

Supabase project `jesqomurskzlegtkzlgm` is configured locally with its publishable key, and the database migrations have been applied. This repository does **not** include a trained DR model, SMTP credentials, backend database credentials, service-role credentials or a live web deployment.
See [AUTH_SETUP.md](AUTH_SETUP.md) for the remaining authentication configuration and verification details.
Configure those services using [DEPLOYMENT.md](DEPLOYMENT.md). The model adapter contract is in [AI_INTEGRATION.md](AI_INTEGRATION.md).
Unconfigured authentication cannot log users in. Unconfigured AI marks analysis unavailable and preserves the image; it never returns a fabricated diagnosis.
The app supports JPEG/PNG, not DICOM. No optional platform SUPER_ADMIN portal is implemented.

## Local setup

Use Node 24, Python 3.12–3.14 (Docker uses 3.13), and uv.

1. Copy `.env.example` to `.env.local`; copy `backend/.env.example` to `backend/.env`. Supply your own configuration.
2. Apply the Supabase migration and set dedicated database-role credentials as described in DEPLOYMENT.md.
3. Run `npm ci` in this directory.
4. Run `uv sync --frozen` inside `backend`.
5. Start the API from `backend` with `uv run python -m app`. This launcher handles Windows async database compatibility.
6. Start the worker in a second backend terminal with `DATABASE_URL` set to the **retina_worker** connection, then `uv run python -m app.worker`.
7. Run `npm run dev` and visit http://localhost:3000.

The browser communicates through Next.js `/api/backend/*`; only Next.js and the worker/API connect to backend services.
No service-role key belongs in a `NEXT_PUBLIC_*` variable.

## Verification

```text
npm run typecheck
npm run lint
npm test
npm run test:db
npm run test:integration
npm run build

# inside backend/
uv run pytest -q
uv run ruff check app tests
```

Browser checks: install the matching Chromium binary with `npx playwright install chromium`, then run `npm run test:e2e`.
On Windows with Edge already installed, set `PLAYWRIGHT_CHANNEL=msedge`.
For an independently running web server, set `PLAYWRIGHT_EXTERNAL_SERVER=true`.
CI runs the production build server separately.

`test:db` executes the real migration in embedded PostgreSQL and verifies tenant isolation, session revocation and privileges.
`test:integration` starts an isolated loopback PostgreSQL fixture, then drives the real FastAPI endpoints and worker through verification and retakes.
Its identity provider, image storage and classifier are **test doubles**, not a demonstration of clinical model performance or live Supabase email delivery.
The integration fixture is never used by the application runtime and contains synthetic data only.

## Design boundaries

One authentication account belongs to one organization. Organization creation is available to verified accounts without membership.
Organization administrators invite doctors/technicians, but cannot create other administrators or issue clinical decisions.
Deactivation blocks API/database access immediately; account passwords remain exclusively with Supabase Auth.
Notifications are polled in-app; no external email/SMS clinical notification service is configured.
Clinical records are append-only. Failed analysis can retry the same image; a retake creates a new screening linked to the previous one.
Patient history is paginated. Operational list views use bounded pages, not unbounded downloads.

See [VERIFICATION.md](VERIFICATION.md) for the verification boundary and outstanding live-service checks.
