"use client";
import { useEffect, useState } from "react";
import { fetchPatients } from "./api";
import type { Patient } from "@/types/domain";
import { ScreeningHistory } from "@/features/screenings/ScreeningHistory";
export function PatientDirectory() {
  const [rows, setRows] = useState<Patient[]>([]);
  const [selected, setSelected] = useState("");
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const timer = setTimeout(() => { fetchPatients({ q: search }).then(data => { if (active) { setRows(data); setError(""); } }).catch(e => { if (active) setError(e.message); }); }, 250);
    return () => { active = false; clearTimeout(timer); };
  }, [search]);
  return <section className="my-6 p-6 rounded-3xl border bg-white"><h2 className="text-xl font-bold mb-4">Patient history</h2>
    <label className="block text-sm mb-3">Search by name or patient ID<input className="block w-full mt-2 border rounded-xl p-3" value={search} onChange={e => setSearch(e.target.value)} placeholder="Search all registered patients" /></label>
    <label className="text-sm">Select patient<select className="block w-full mt-2 border rounded-xl p-3" value={selected} onChange={e => setSelected(e.target.value)}>
      <option value="">Choose a patient</option>{rows.map(p => <option key={p.id} value={p.id}>{p.fullName} · {p.mrn}</option>)}
    </select></label>{error && <p role="alert">{error}</p>}{selected && <ScreeningHistory key={selected} patientId={selected} />}</section>;
}
