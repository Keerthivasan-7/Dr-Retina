import "server-only";
import { apiServer } from "@/lib/api/server";
import { ApiError } from "@/lib/api/errors";
import type { Role } from "./permissions";
export interface Session { userId: string; email: string; role: Role; orgId: string; orgName: string; }
export async function getSession(): Promise<Session | null> {
  try { return await apiServer<Session>("/me"); }
  catch (error) {
    if (error instanceof ApiError && [401, 403].includes(error.status)) return null;
    throw error;
  }
}
