import "server-only";
import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
export async function createSupabaseServerClient() {
  const store = await cookies();
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ?? process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !key) throw new Error("Authentication is not configured");
  return createServerClient(url, key, { cookies: {
    getAll: () => store.getAll(),
    setAll: (values) => {
      try { values.forEach(({ name, value, options }) => store.set(name, value, options)); }
      catch { /* Server Components are read-only; proxy refreshes cookies. */ }
    },
  } });
}
