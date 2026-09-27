"use client";
import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
import { OrganizationForm } from "./OrganizationForm";
export function OrganizationSettings() {
  const [org, setOrg] = useState<Record<string, string> | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    apiClient<{ data: Record<string, string> }>("/organization").then(r => setOrg({
      ...r.data, contactEmail: r.data.contact_email ?? "", contactPhone: r.data.contact_phone ?? "",
    })).catch(e => setError(e.message));
  }, []);
  return <div className="my-6">{error ? <p role="alert">{error}</p> : org ? <OrganizationForm existing={org} /> : <p>Loading organization settings…</p>}</div>;
}

