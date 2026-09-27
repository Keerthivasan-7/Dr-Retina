"use client";
import { apiClient } from "@/lib/api/client";
import type { Organization } from "@/types/domain";
export async function fetchOrganizations(): Promise<Organization[]> {
  return (await apiClient<{ data: Organization[] }>("/organizations")).data;
}
