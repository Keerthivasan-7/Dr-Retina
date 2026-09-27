import { PGlite } from "@electric-sql/pglite";
import fs from "node:fs";
import assert from "node:assert/strict";
const db = new PGlite();
await db.exec(`
  create role anon; create role authenticated;
  create schema auth;
  create table auth.users(id uuid primary key);
  create table auth.sessions(id uuid primary key,user_id uuid,not_after timestamptz);
  create schema storage;
  create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
`);
const migration = fs.readdirSync("supabase/migrations").find(p => p.endsWith("_clinical_workflow.sql"));
await db.exec(fs.readFileSync("supabase/migrations/" + migration,"utf8"));
const ids = Array.from({length:14}, (_,i)=>`00000000-0000-4000-8000-${String(i+1).padStart(12,"0")}`);
const [a,b,ad,bd,at,bt,as,bs,ao,bo,ap,bp,screen,otherScreen] = ids;
await db.exec(`
 insert into auth.users values ('${a}'),('${b}'),('${ad}'),('${bd}'),('${at}'),('${bt}');
 insert into auth.sessions values ('${as}','${a}',null),('${bs}','${b}',null);
 insert into retina.organizations(id,name,type,address,contact_email,identifier,created_by) values
 ('${ao}','Clinic A','Clinic','A','a@example.org','A','${a}'),('${bo}','Clinic B','Clinic','B','b@example.org','B','${b}');
 insert into retina.members(user_id,org_id,email,full_name,role) values
 ('${a}','${ao}','a@example.org','Admin A','ORG_ADMIN'),('${b}','${bo}','b@example.org','Admin B','ORG_ADMIN'),
 ('${ad}','${ao}','ad@example.org','Doctor A','DOCTOR'),('${bd}','${bo}','bd@example.org','Doctor B','DOCTOR'),
 ('${at}','${ao}','at@example.org','Tech A','LAB_TECHNICIAN'),('${bt}','${bo}','bt@example.org','Tech B','LAB_TECHNICIAN');
 insert into retina.patients(id,org_id,mrn,full_name,age,gender,registered_by) values
 ('${ap}','${ao}','A1','Patient A',50,'Female','${at}'),('${bp}','${bo}','B1','Patient B',51,'Male','${bt}');
 insert into retina.screenings(id,org_id,patient_id,created_by,eye) values
 ('${screen}','${ao}','${ap}','${at}','OD'),('${otherScreen}','${bo}','${bp}','${bt}','OS');
 insert into retina.ai_results(org_id,screening_id,severity,confidence,probabilities,model_version) values
 ('${ao}','${screen}','No DR',0.8,'{}','test-v1'),('${bo}','${otherScreen}','Mild NPDR',0.8,'{}','test-v1');
 insert into retina.images(org_id,screening_id,object_path,sha256,mime,width,height) values
 ('${ao}','${screen}','A/original','a','image/png',300,300),('${bo}','${otherScreen}','B/original','b','image/png',300,300);
 set role retina_api;
 select set_config('app.user_id','${a}',false),set_config('app.session_id','${as}',false);
`);
let checks=0;
async function count(sql, expected) { const r=await db.query(sql); assert.equal(r.rows.length,expected); checks++; }
async function denied(sql) { await assert.rejects(db.exec(sql)); checks++; }
await count("select * from retina.patients",1);
await count("select * from retina.members",3);
await count("select * from retina.organizations",1);
await count("select * from retina.ai_results",1);
await count("select * from retina.images",1);
await count(`select * from retina.patients where id='${bp}'`,0);
await denied(`insert into retina.patients(org_id,mrn,full_name,age,gender,registered_by) values('${bo}','ATTACK','Intrusion',50,'Female','${bt}')`);
await denied(`insert into retina.screenings(org_id,patient_id,created_by,eye) values('${ao}','${bp}','${at}','OD')`);
await denied(`update retina.ai_results set severity='No DR'`);
await denied(`delete from retina.images`);
await denied(`update retina.reviews set final_assessment='overwrite'`);
await denied(`delete from retina.audit_events`);
await db.exec(`select set_config('app.session_id','${bs}',false)`);
await count("select * from retina.patients",0);
await db.exec(`select set_config('app.user_id','${b}',false)`);
await count("select * from retina.patients",1);
await db.exec(`reset role; update retina.members set active=false where user_id='${b}'; set role retina_api`);
await count("select * from retina.patients",0);
await db.exec(`reset role; update retina.members set active=true where user_id='${b}'; delete from auth.sessions where id='${bs}'; set role retina_api`);
await count("select * from retina.patients",0);
await db.exec("reset role; set role authenticated");
await denied("select * from retina.patients");
await denied("select retina_private.org_id()");
await db.exec("reset role; set role retina_worker");
await denied("update retina.members set role='ORG_ADMIN'");
await denied("insert into retina.reviews(org_id,screening_id,doctor_id,decision) values(null,null,null,'VERIFIED')");
await count("select * from retina.jobs",0);
// Verify organization bootstrap under an authenticated, non-member user.
await db.exec(`reset role;
 insert into auth.users values('10000000-0000-4000-8000-000000000001');
 insert into auth.sessions values('10000000-0000-4000-8000-000000000002','10000000-0000-4000-8000-000000000001',null);
 set role retina_api;
 select set_config('app.user_id','10000000-0000-4000-8000-000000000001',false),
 set_config('app.session_id','10000000-0000-4000-8000-000000000002',false);
 insert into retina.organizations(id,name,type,address,contact_email,identifier,created_by)
 values('10000000-0000-4000-8000-000000000003','New clinic','Clinic','New','new@example.org','NEW','10000000-0000-4000-8000-000000000001');
 insert into retina.members(user_id,org_id,email,full_name,role)
 values('10000000-0000-4000-8000-000000000001','10000000-0000-4000-8000-000000000003','new@example.org','New admin','ORG_ADMIN');
`);
await count("select * from retina.organizations",1);
await count("select * from retina.patients",0);
await db.close();
console.log(`${checks} PostgreSQL isolation, session revocation, privilege, and onboarding checks passed.`);

