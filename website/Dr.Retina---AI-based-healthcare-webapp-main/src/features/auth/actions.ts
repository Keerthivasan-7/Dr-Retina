"use server";
import { redirect } from "next/navigation";
import { z } from "zod";
import { createSupabaseServerClient } from "@/lib/auth/supabase";
import { getSession } from "@/lib/auth/session";
import { defaultRouteForRole } from "@/lib/auth/permissions";
import { authErrorMessage } from "@/lib/auth/messages";
export async function loginAction(form: FormData) {
  const parsed = z.object({ email: z.email(), password: z.string().min(1).max(256) })
    .safeParse({ email: form.get("email"), password: form.get("password") });
  if (!parsed.success) return { ok: false as const, error: "Enter a valid email and password." };
  let destination = "/onboarding";
  try {
    const client = await createSupabaseServerClient();
    const { error } = await client.auth.signInWithPassword(parsed.data);
    if (error) return { ok: false as const, error: authErrorMessage(error, "Sign-in failed. Check your credentials and email verification.") };
    try {
      const session = await getSession();
      if (session) destination = defaultRouteForRole(session.role);
    } catch { destination = "/account?notice=organization_unavailable"; }
  } catch { return { ok: false as const, error: "Authentication is unavailable. Contact your administrator." }; }
  redirect(destination);
}
export async function logoutAction() {
  let failed = false;
  try {
    const client = await createSupabaseServerClient();
    const { error } = await client.auth.signOut({ scope: "global" });
    failed = !!error;
  } catch { failed = true; }
  if (failed) redirect("/login?error=logout_failed");
  redirect("/login");
}
export async function requestPasswordReset(form: FormData) {
  const email = z.email().safeParse(form.get("email"));
  if (!email.success) return { error: "Enter a valid email." };
  try {
    const client = await createSupabaseServerClient();
    const { error } = await client.auth.resetPasswordForEmail(email.data, {
      redirectTo: `${process.env.APP_URL ?? "http://localhost:3000"}/auth/callback?next=/account/password`,
    });
    if (error) return { error: authErrorMessage(error, "Password recovery is currently unavailable.") };
  } catch { return { error: "Password recovery is currently unavailable." }; }
  return { message: "If the account exists, a recovery email will be sent." };
}
export async function changePassword(form: FormData) {
  const password = z.string().min(12).max(128).safeParse(form.get("password"));
  if (!password.success) return { error: "Use a password containing 12–128 characters." };
  try {
    const client = await createSupabaseServerClient();
    const { data: { user }, error: authError } = await client.auth.getUser();
    if (authError || !user) return { error: "Open your invitation or recovery link first, or sign in." };
    const { error } = await client.auth.updateUser({ password: password.data });
    if (error) return { error: authErrorMessage(error, "Password could not be updated. Request a fresh recovery link.") };
    const { error: signOutError } = await client.auth.signOut({ scope: "global" });
    if (signOutError) return { message: "Password updated, but signing out all sessions failed. Please try signing out again." };
    return { message: "Password updated. Sign in with your new password." };
  } catch { return { error: "Password update is unavailable." }; }
}
export async function registerOrganizationAccount(form: FormData) {
  const parsed = z.object({ email: z.email(), password: z.string().min(12).max(128) })
    .safeParse({ email: form.get("email"), password: form.get("password") });
  if (!parsed.success) return { error: "Use a valid email and a password of at least 12 characters." };
  try {
    const client = await createSupabaseServerClient();
    const { error } = await client.auth.signUp({ ...parsed.data,
      options: { emailRedirectTo: `${process.env.APP_URL ?? "http://localhost:3000"}/auth/callback?next=/onboarding` } });
    if (error) return { error: authErrorMessage(error, "Account setup failed. Try signing in or recovering your password.") };
    return { message: "Check your email to verify your account, then sign in to create your organization." };
  } catch { return { error: "Authentication is not configured yet." }; }
}
export async function resendVerification(form: FormData) {
  const email = z.email().safeParse(form.get("email"));
  if (!email.success) return { error: "Enter a valid email." };
  try {
    const client = await createSupabaseServerClient();
    const { error } = await client.auth.resend({ type: "signup", email: email.data,
      options: { emailRedirectTo: `${process.env.APP_URL ?? "http://localhost:3000"}/auth/callback?next=/onboarding` } });
    if (error) return { error: authErrorMessage(error, "Verification email is currently unavailable.") };
    return { message: "If your account needs verification, a new email will be sent." };
  } catch { return { error: "Verification email is currently unavailable." }; }
}
export async function confirmEmailAction(form: FormData) {
  const parsed = z.object({
    token_hash: z.string().min(1),
    type: z.enum(["invite", "recovery", "signup"]),
  }).safeParse({ token_hash: form.get("token_hash"), type: form.get("type") });
  if (!parsed.success) redirect("/login?error=invalid_link");
  let verified = false;
  try {
    const client = await createSupabaseServerClient();
    const { error } = await client.auth.verifyOtp(parsed.data);
    verified = !error;
  } catch { /* Never expose token or provider internals. */ }
  // redirect() must run outside the try/catch above: it throws internally to
  // interrupt rendering, which the catch block would otherwise swallow.
  if (verified) redirect(parsed.data.type === "signup" ? "/onboarding" : "/account/password");
  redirect("/login?error=invalid_link");
}
export async function exchangeCodeAction(form: FormData) {
  const parsed = z.object({
    code: z.string().min(1),
    next: z.enum(["/onboarding", "/account/password"]),
  }).safeParse({ code: form.get("code"), next: form.get("next") });
  if (!parsed.success) redirect("/login?error=invalid_link");
  let exchanged = false;
  try {
    const client = await createSupabaseServerClient();
    const { error } = await client.auth.exchangeCodeForSession(parsed.data.code);
    exchanged = !error;
  } catch { /* Never expose the code or provider internals. */ }
  // redirect() must run outside the try/catch above; see confirmEmailAction.
  if (exchanged) redirect(parsed.data.next);
  redirect("/login?error=invalid_link");
}
export async function updateProfile(form: FormData) {
  const name = z.string().trim().max(100).safeParse(form.get("displayName"));
  if (!name.success) return { error: "Use a display name of up to 100 characters." };
  try {
    const client = await createSupabaseServerClient();
    const { data: { user }, error: authError } = await client.auth.getUser();
    if (authError || !user) return { error: "Sign in to update your profile." };
    const { data, error } = await client.from("profiles").update({ display_name: name.data }).eq("id", user.id).select("id").single();
    if (error || !data) return { error: "Your profile could not be saved. Please try again." };
    return { message: "Profile saved." };
  } catch { return { error: "Profile service is temporarily unavailable." }; }
}
