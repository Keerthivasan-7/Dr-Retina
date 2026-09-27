# Verification record

The following checks are available and were exercised locally during implementation:

Last local verification: 25 September 2026. Results: 18 frontend tests, 37 backend tests, one separate full-workflow integration test, 23 database isolation checks, and six browser tests passed. TypeScript, ESLint, Ruff, and the production build passed. The backend unit run skips the integration test unless its database is supplied; `npm run test:integration` supplies it and passed separately. `npm audit --omit=dev` reported zero known production dependency vulnerabilities.

- TypeScript and ESLint for the web application.
- Frontend unit tests covering permissions, schemas, severity presentation, bounded uploads, and separate doctor decisions.
- Backend tests covering RBAC, authentication rejection, state transitions, upload validation, model-response validation, stale workers and quality rejection.
- Embedded PostgreSQL tests applying the migration and checking two-tenant isolation, inactive membership, revoked sessions, immutable records and onboarding.
- A full HTTP API + PostgreSQL + worker integration test: register patient, idempotent retry, upload original image, classify, assign doctor, verify, finalize, request more analysis, retake, and revoke access.
- Browser checks for landing/mobile layout, login/recovery navigation, onboarding, rejection of forged prototype cookies, and API authentication/CSRF boundaries.
- A Next.js production build.

## What the tests do not establish

Supabase Auth, SMTP, object storage and the classifier are replaced by controlled synthetic fixtures in the integrated workflow test.
PostgreSQL engine/RLS behavior is exercised through PGlite; real server connection pooling and multi-worker concurrency still need deployment-environment tests.
Browser tests do not log into a real Supabase account.
No trained model, backend secret credentials, Docker daemon, hosting target, or complete requirements after the truncated “12. PA” section were supplied.
The authentication follow-up applied migrations to `jesqomurskzlegtkzlgm` and verified profile isolation in hosted PostgreSQL using rolled-back test users. The hosted security advisor returned no findings. Production email delivery, hosted web deployment, backup restoration, and clinical accuracy validation have not been performed.

Before treating this as a deployed clinical system, complete the live acceptance steps in DEPLOYMENT.md.
