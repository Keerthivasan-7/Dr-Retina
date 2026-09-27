// Synthetic PostgreSQL integration fixture. Never use this server for application data.
import { PGlite } from "@electric-sql/pglite";
import { PGLiteSocketServer } from "@electric-sql/pglite-socket";
import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
const db = await PGlite.create();
await db.exec(`
create role anon; create role authenticated;
create schema auth;
create table auth.users(id uuid primary key);
create function auth.uid() returns uuid language sql stable as $$ select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid $$;
create table auth.sessions(id uuid primary key,user_id uuid,not_after timestamptz);
create schema storage;
create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
`);
for (const name of fs.readdirSync("supabase/migrations").filter(n => n.endsWith(".sql")).sort()) {
  await db.exec(fs.readFileSync(path.join("supabase/migrations",name),"utf8"));
}
const server = new PGLiteSocketServer({ db, host:"127.0.0.1", port:55439 });
await server.start();
const python = process.platform === "win32" ? ".venv/Scripts/python.exe" : ".venv/bin/python";
try {
  const code = await new Promise((resolve,reject) => {
    const child = spawn(path.resolve("backend",python), ["-m","pytest","tests/test_integration.py","-q"], {
      cwd:path.resolve("backend"), stdio:"inherit", windowsHide:true,
      env:{...process.env, TEST_DATABASE_URL:"postgresql://postgres@127.0.0.1:55439/postgres?sslmode=disable"},
    });
    child.once("error",reject); child.once("exit",resolve);
  });
  process.exitCode=code ?? 1;
} finally { await server.stop(); await db.close(); }
