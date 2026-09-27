"use client";
import { useCallback, useEffect, useState } from "react";
import { apiClient } from "@/lib/api/client";
type Member = { user_id: string; full_name: string; email: string; role: string; active: boolean; available: boolean };
export function UsersPanel() {
  const [users, setUsers] = useState<Member[]>([]);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(() => { apiClient<{ data: Member[] }>("/users").then(r => setUsers(r.data)).catch(e => setMessage(e.message)); }, []);
  useEffect(() => { refresh(); }, [refresh]);
  async function change(user: Member, values: Partial<Member>) {
    setBusy(true); try {
      await apiClient(`/users/${user.user_id}`, { method: "PATCH", body: { active: user.active, role: user.role, available: user.available, ...values } });
      refresh(); setMessage("Access updated.");
    } catch (e) { setMessage(e instanceof Error ? e.message : "Update failed"); } finally { setBusy(false); }
  }
  return <section className="bg-white border border-brand-100 rounded-3xl p-6 my-6">
    <h2 className="text-xl font-bold">Authorized team</h2>
    <form className="grid sm:grid-cols-2 gap-3 my-5" method="post" onSubmit={async e => {
      e.preventDefault(); const form = e.currentTarget; const data = Object.fromEntries(new FormData(form)); setBusy(true);
      try { await apiClient("/users/invite", { method: "POST", body: data }); form.reset(); refresh(); setMessage("Invitation sent. The user sets their own password."); }
      catch (e) { setMessage(e instanceof Error ? e.message : "Invitation failed"); } finally { setBusy(false); }
    }}>
      <label className="text-sm">Full name<input name="fullName" required maxLength={120} className="block w-full border p-3 rounded-xl mt-1" /></label>
      <label className="text-sm">Email<input name="email" type="email" required className="block w-full border p-3 rounded-xl mt-1" /></label>
      <label className="text-sm">Role<select name="role" className="block w-full border p-3 rounded-xl mt-1"><option value="LAB_TECHNICIAN">Lab technician</option><option value="DOCTOR">Doctor</option></select></label>
      <button disabled={busy} className="self-end rounded-xl bg-brand-600 text-white p-3 disabled:opacity-50">Invite user</button>
    </form>
    {message && <p role="status" className="text-sm my-3">{message}</p>}
    <div className="space-y-3">{users.map(user => <div key={user.user_id} className="border rounded-xl p-4 flex flex-wrap justify-between items-center gap-3">
      <div><p className="font-semibold">{user.full_name}</p><p className="text-sm text-slate-500">{user.email} · {user.active ? "Authorized" : "Access revoked"}</p></div>
      {user.role !== "ORG_ADMIN" ? <div className="flex flex-wrap gap-2">
        <select aria-label={`Role for ${user.full_name}`} disabled={busy} value={user.role} onChange={e => void change(user, { role: e.target.value })} className="border rounded-lg p-2 text-sm"><option value="LAB_TECHNICIAN">Lab technician</option><option value="DOCTOR">Doctor</option></select>
        <button disabled={busy} onClick={() => void change(user, { active: !user.active })} className="border rounded-lg p-2 text-sm">{user.active ? "Revoke access" : "Activate"}</button>
        <button disabled={busy} onClick={async () => { setBusy(true); try { await apiClient(`/users/${user.user_id}/reset-password`, { method: "POST" }); setMessage("Recovery email requested."); } catch (e) { setMessage(e instanceof Error ? e.message : "Recovery failed"); } finally { setBusy(false); } }} className="border rounded-lg p-2 text-sm">Send password reset</button>
      </div> : <span className="text-sm text-brand-700">Organization administrator</span>}
    </div>)}</div>
  </section>;
}
