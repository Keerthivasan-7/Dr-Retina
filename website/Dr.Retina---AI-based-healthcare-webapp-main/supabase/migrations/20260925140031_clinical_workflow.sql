-- Application tables are deliberately NOT exposed through the Supabase Data API.
create schema if not exists retina;
create schema if not exists retina_private;
do $$ begin
  if not exists(select 1 from pg_roles where rolname='retina_api') then
    create role retina_api login nosuperuser nobypassrls;
  end if;
  if not exists(select 1 from pg_roles where rolname='retina_worker') then
    create role retina_worker login nosuperuser nobypassrls;
  end if;
end $$;
revoke all on schema retina, retina_private from public, anon, authenticated;
grant usage on schema retina, retina_private to retina_api, retina_worker;
alter default privileges in schema retina revoke all on tables from public, anon, authenticated;
alter default privileges in schema retina_private revoke execute on functions from public;

create table retina.organizations (
  id uuid primary key default gen_random_uuid(),
  name text not null, type text not null, address text not null,
  contact_email text not null, contact_phone text not null default '',
  identifier text not null unique, active boolean not null default true,
  created_by uuid not null references auth.users(id), created_at timestamptz not null default now()
);
create table retina.members (
  user_id uuid primary key references auth.users(id),
  org_id uuid not null references retina.organizations(id),
  email text not null, full_name text not null,
  role text not null check(role in ('ORG_ADMIN','DOCTOR','LAB_TECHNICIAN')),
  active boolean not null default true, available boolean not null default true,
  invited_at timestamptz not null default now(), unique(org_id,user_id), unique(org_id,email)
);
create table retina.patients (
  id uuid primary key default gen_random_uuid(), org_id uuid not null references retina.organizations(id),
  mrn text not null, full_name text not null, age int not null check(age between 0 and 120),
  gender text not null check(gender in ('Female','Male','Other')),
  date_of_birth date, contact_number text not null default '', address text not null default '',
  clinical_history text not null default '', diabetes_duration_years numeric not null default 0,
  known_diabetic text not null default 'Unknown', camp_location text not null default '',
  registered_by uuid not null, created_at timestamptz not null default now(),
  unique(org_id,id), unique(org_id,mrn),
  foreign key(org_id,registered_by) references retina.members(org_id,user_id)
);
create table retina.screenings (
  id uuid primary key default gen_random_uuid(), org_id uuid not null references retina.organizations(id),
  patient_id uuid not null, created_by uuid not null, eye text not null check(eye in ('OD','OS')),
  status text not null default 'PATIENT_REGISTERED' check(status in (
    'PATIENT_REGISTERED','IMAGE_UPLOADED','QUALITY_CHECKING','QUALITY_REJECTED','READY_FOR_ANALYSIS',
    'AI_PROCESSING','REPORT_READY','SENT_TO_DOCTOR','DOCTOR_REVIEWING','VERIFIED',
    'ADDITIONAL_ANALYSIS_REQUIRED','COMPLETED')),
  parent_screening_id uuid, assigned_doctor_id uuid, assigned_at timestamptz,
  assignment_status text not null default 'UNASSIGNED' check(assignment_status in ('UNASSIGNED','QUEUED','ASSIGNED')),
  created_at timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique(org_id,id),
  foreign key(org_id,patient_id) references retina.patients(org_id,id),
  foreign key(org_id,created_by) references retina.members(org_id,user_id),
  foreign key(org_id,assigned_doctor_id) references retina.members(org_id,user_id),
  foreign key(org_id,parent_screening_id) references retina.screenings(org_id,id)
);
create table retina.images (
  id uuid primary key default gen_random_uuid(), org_id uuid not null,
  screening_id uuid not null, object_path text not null unique,
  sha256 text not null, mime text not null, width int not null, height int not null,
  created_at timestamptz not null default now(), unique(org_id,screening_id),
  foreign key(org_id,screening_id) references retina.screenings(org_id,id)
);
create table retina.quality_results (
  id uuid primary key default gen_random_uuid(), org_id uuid not null, screening_id uuid not null,
  score numeric not null check(score between 0 and 1), accepted boolean not null,
  reasons jsonb not null, model_version text not null, created_at timestamptz not null default now(),
  unique(org_id,screening_id), foreign key(org_id,screening_id) references retina.screenings(org_id,id)
);
create table retina.ai_results (
  id uuid primary key default gen_random_uuid(), org_id uuid not null, screening_id uuid not null,
  severity text not null, confidence numeric not null check(confidence between 0 and 1),
  probabilities jsonb not null, model_version text not null, explainability_path text,
  findings jsonb not null default '[]', created_at timestamptz not null default now(),
  unique(org_id,screening_id), foreign key(org_id,screening_id) references retina.screenings(org_id,id)
);
create table retina.reviews (
  id uuid primary key default gen_random_uuid(), org_id uuid not null, screening_id uuid not null,
  doctor_id uuid not null, decision text not null check(decision in ('VERIFIED','ADDITIONAL_ANALYSIS_REQUIRED')),
  final_assessment text not null default '', comments text not null default '', reason text,
  created_at timestamptz not null default now(), unique(org_id,screening_id),
  foreign key(org_id,screening_id) references retina.screenings(org_id,id),
  foreign key(org_id,doctor_id) references retina.members(org_id,user_id),
  check((decision='VERIFIED' and length(trim(final_assessment))>0) or
        (decision='ADDITIONAL_ANALYSIS_REQUIRED' and reason is not null and length(trim(comments))>0))
);
create table retina.screening_events (
  id uuid primary key default gen_random_uuid(), org_id uuid not null, screening_id uuid not null,
  actor_id uuid, status text not null, created_at timestamptz not null default now(),
  foreign key(org_id,screening_id) references retina.screenings(org_id,id)
);
create table retina.jobs (
  id uuid primary key default gen_random_uuid(), org_id uuid not null, screening_id uuid not null,
  state text not null default 'QUEUED' check(state in ('QUEUED','RUNNING','DONE','FAILED')),
  attempts int not null default 0, lease_until timestamptz, lease_token uuid,
  error_code text, created_at timestamptz not null default now(), unique(org_id,screening_id),
  foreign key(org_id,screening_id) references retina.screenings(org_id,id)
);
create table retina.notifications (
  id uuid primary key default gen_random_uuid(), org_id uuid not null, user_id uuid not null,
  screening_id uuid not null, message text not null, read_at timestamptz,
  created_at timestamptz not null default now(),
  foreign key(org_id,user_id) references retina.members(org_id,user_id),
  foreign key(org_id,screening_id) references retina.screenings(org_id,id)
);
create table retina.audit_events (
  id uuid primary key default gen_random_uuid(), org_id uuid not null references retina.organizations(id),
  actor_id uuid not null, action text not null, resource_id uuid,
  created_at timestamptz not null default now()
);
create table retina.idempotency (
  org_id uuid not null references retina.organizations(id), user_id uuid not null,
  key uuid not null, operation text not null, fingerprint text not null, response jsonb not null,
  created_at timestamptz not null default now(), primary key(org_id,user_id,key,operation)
);

-- Narrow lookup helpers live in a private schema; no browser role can call them.
create function retina_private.session_active() returns boolean language sql stable
security definer set search_path='' as $$
 select exists(select 1 from auth.sessions s
   where s.id=nullif(current_setting('app.session_id',true),'')::uuid
   and s.user_id=nullif(current_setting('app.user_id',true),'')::uuid
   and (s.not_after is null or s.not_after>now()))
$$;
create function retina_private.org_id() returns uuid language sql stable
security definer set search_path='' as $$
 select m.org_id from retina.members m join retina.organizations o on o.id=m.org_id
 where m.user_id=nullif(current_setting('app.user_id',true),'')::uuid
 and m.active and o.active and retina_private.session_active()
$$;
create function retina_private.role() returns text language sql stable
security definer set search_path='' as $$
 select m.role from retina.members m where m.user_id=nullif(current_setting('app.user_id',true),'')::uuid
 and m.active and m.org_id=retina_private.org_id()
$$;
revoke all on all functions in schema retina_private from public, anon, authenticated;
grant execute on all functions in schema retina_private to retina_api;

do $$ declare t text; begin
 foreach t in array array['organizations','members','patients','screenings','images','quality_results',
 'ai_results','reviews','screening_events','jobs','notifications','audit_events','idempotency'] loop
   execute format('alter table retina.%I enable row level security',t);
   execute format('alter table retina.%I force row level security',t);
 end loop;
 foreach t in array array['patients','screenings','images','quality_results','ai_results','reviews',
 'screening_events','jobs','notifications','audit_events','idempotency'] loop
   execute format('create policy tenant_boundary on retina.%I to retina_api
     using (org_id=(select retina_private.org_id()))
     with check (org_id=(select retina_private.org_id()))',t);
 end loop;
end $$;
create policy org_read on retina.organizations for select to retina_api
 using(id=(select retina_private.org_id()) or
       (created_by=nullif(current_setting('app.user_id',true),'')::uuid and retina_private.session_active()));
create policy org_create on retina.organizations for insert to retina_api
 with check(created_by=nullif(current_setting('app.user_id',true),'')::uuid and
            retina_private.session_active() and retina_private.org_id() is null);
create policy org_update on retina.organizations for update to retina_api
 using(id=retina_private.org_id() and retina_private.role()='ORG_ADMIN')
 with check(id=retina_private.org_id() and retina_private.role()='ORG_ADMIN');
create policy members_read on retina.members for select to retina_api
 using(org_id=retina_private.org_id());
create policy members_create on retina.members for insert to retina_api with check(
 (org_id=retina_private.org_id() and retina_private.role()='ORG_ADMIN' and role in ('DOCTOR','LAB_TECHNICIAN'))
 or (user_id=nullif(current_setting('app.user_id',true),'')::uuid and role='ORG_ADMIN'
     and retina_private.session_active() and exists(select 1 from retina.organizations o
       where o.id=org_id and o.created_by=user_id)));
create policy members_update on retina.members for update to retina_api
 using(org_id=retina_private.org_id() and
  ((retina_private.role()='ORG_ADMIN' and role in ('DOCTOR','LAB_TECHNICIAN')) or
   (user_id=nullif(current_setting('app.user_id',true),'')::uuid and role='DOCTOR')))
 with check(org_id=retina_private.org_id());

grant select,insert,update on retina.organizations,retina.members to retina_api;
grant select,insert on retina.patients,retina.images,retina.reviews,retina.screening_events,
 retina.audit_events,retina.idempotency to retina_api;
grant select,insert,update on retina.screenings,retina.jobs,retina.notifications to retina_api;
grant select on retina.ai_results,retina.quality_results to retina_api;
-- No API grant can alter or delete an image, AI result, quality result, review, or audit event.
do $$ declare t text; begin
 foreach t in array array['organizations','members','screenings','images','quality_results',
 'ai_results','screening_events','jobs','notifications'] loop
   execute format('create policy trusted_worker on retina.%I to retina_worker using(true) with check(true)',t);
 end loop;
end $$;
grant select on retina.organizations,retina.members,retina.images to retina_worker;
grant select,update on retina.screenings,retina.jobs to retina_worker;
grant select,insert on retina.quality_results,retina.ai_results,retina.screening_events,retina.notifications to retina_worker;
-- Worker cannot change membership, patients, or clinical reviews.
create index members_org_role on retina.members(org_id,role) where active;
create index patients_org_date on retina.patients(org_id,created_at desc);
create index screenings_org_status on retina.screenings(org_id,status,created_at desc);
create index screenings_org_patient on retina.screenings(org_id,patient_id,created_at desc);
create index screenings_doctor on retina.screenings(assigned_doctor_id,status);
create index jobs_claim on retina.jobs(state,lease_until,created_at);
create index notifications_inbox on retina.notifications(org_id,user_id,created_at desc);
create index screening_events_history on retina.screening_events(org_id,screening_id,created_at);
create index audit_org_date on retina.audit_events(org_id,created_at desc);

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('retinal-images','retinal-images',false,26214400,array['image/jpeg','image/png'])
on conflict(id) do nothing;
-- No storage.objects policy grants browser access: all bytes pass through authenticated FastAPI.
