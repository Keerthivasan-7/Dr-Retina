import "server-only";
import { redirect } from "next/navigation";
import { getSession } from "./session";
import { defaultRouteForRole, hasPermission, type Role } from "./permissions";

/** Require any authenticated session; redirect to /login otherwise. */
export async function requireSession() {
  const session = await getSession();
  if (!session) redirect("/login");
  return session;
}

/** Require one of the allowed roles; redirect to the user's home otherwise. */
export async function requireRole(...allowed: Role[]) {
  const session = await requireSession();
  if (!allowed.includes(session.role)) redirect(defaultRouteForRole(session.role));
  return session;
}

/** Permission check helper for server code (proxy performs only light routing). */
export function requirePermission(role: Role, permission: string): void {
  if (!hasPermission(role, permission)) {
    throw new Error(`Forbidden: missing permission ${permission}`);
  }
}
