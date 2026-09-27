import { z } from "zod";

export const RoleSchema = z.enum(["ORG_ADMIN", "DOCTOR", "LAB_TECHNICIAN"]);
export type Role = z.infer<typeof RoleSchema>;

/** Legacy UI role ids (doctor | lab_tech | admin) mapped to canonical roles. */
export function normalizeRole(input: string | null | undefined): Role | null {
  switch ((input ?? "").toLowerCase()) {
    case "org_admin":
    case "admin":
      return "ORG_ADMIN";
    case "doctor":
      return "DOCTOR";
    case "lab_technician":
    case "lab_tech":
    case "lab-tech":
    case "labtech":
      return "LAB_TECHNICIAN";
    default:
      return null;
  }
}

export const PERMISSIONS = {
  ORG_ADMIN: ["users:manage", "camps:manage", "patients:read", "analytics:read", "audit:read"],
  DOCTOR: ["queue:read", "patients:read", "reviews:write", "reports:read", "reports:write"],
  LAB_TECHNICIAN: ["patients:write", "screenings:write", "screenings:read"],
} as const satisfies Record<Role, readonly string[]>;

export type Permission = (typeof PERMISSIONS)[Role][number];

export function hasPermission(role: Role, permission: string): boolean {
  return (PERMISSIONS[role] as readonly string[]).includes(permission);
}

export function defaultRouteForRole(role: Role): string {
  switch (role) {
    case "ORG_ADMIN":
      return "/admin";
    case "DOCTOR":
      return "/doctor";
    case "LAB_TECHNICIAN":
      return "/lab";
  }
}
