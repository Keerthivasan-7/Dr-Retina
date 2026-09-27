import "server-only";
import { createSupabaseServerClient } from "@/lib/auth/supabase";
import { ApiError } from "./errors";
export async function backendToken(): Promise<string | null> {
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL) return null;
  const client = await createSupabaseServerClient();
  const { data: { user }, error } = await client.auth.getUser();
  if (error || !user) return null;
  // Token transport only, after remote user verification; never authorize from getSession.
  const { data: { session } } = await client.auth.getSession();
  return session?.access_token ?? null;
}
export async function apiServer<T>(endpoint: string, init: RequestInit = {}): Promise<T> {
  const token = await backendToken();
  if (!token) throw new ApiError({ message: "Sign in to continue", status: 401 });
  const response = await fetch((process.env.API_INTERNAL_BASE_URL ?? "http://localhost:8000/api/v1") + endpoint, {
    ...init, cache: "no-store", signal: AbortSignal.timeout(15000),
    headers: { ...init.headers, Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new ApiError({ message: body.message ?? "Service unavailable", status: response.status });
  }
  return response.json() as Promise<T>;
}
