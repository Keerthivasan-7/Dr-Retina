import { beforeEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({ auth: {
  signInWithPassword: vi.fn(), signUp: vi.fn(), signOut: vi.fn(), getUser: vi.fn(),
  updateUser: vi.fn(), resetPasswordForEmail: vi.fn(), resend: vi.fn(), verifyOtp: vi.fn(),
  exchangeCodeForSession: vi.fn(),
}, session: vi.fn() }));
vi.mock("@/lib/auth/supabase", () => ({ createSupabaseServerClient: async () => ({ auth: mocks.auth }) }));
vi.mock("@/lib/auth/session", () => ({ getSession: mocks.session }));
vi.mock("next/navigation", () => ({ redirect: (url: string) => { throw new Error(`REDIRECT:${url}`); } }));
import { changePassword, confirmEmailAction, exchangeCodeAction, loginAction, logoutAction, registerOrganizationAccount, requestPasswordReset, resendVerification } from "@/features/auth/actions";
function form(values: Record<string,string>) { const f = new FormData(); Object.entries(values).forEach(([k,v])=>f.set(k,v)); return f; }
beforeEach(() => { vi.resetAllMocks(); Object.values(mocks.auth).forEach(fn => fn.mockResolvedValue({error:null})); });
describe("Supabase authentication actions", () => {
  it("registers using only credentials, without granting metadata roles", async () => {
    const result=await registerOrganizationAccount(form({email:"new@example.org",password:"a-strong-password",role:"ORG_ADMIN"}));
    expect(result.message).toContain("verify");
    expect(mocks.auth.signUp.mock.calls[0]![0]).not.toHaveProperty("role");
    expect(mocks.auth.signUp.mock.calls[0]![0].options).not.toHaveProperty("data");
  });
  it("rejects invalid registration before contacting Supabase", async () => {
    expect((await registerOrganizationAccount(form({email:"bad",password:"short"}))).error).toBeTruthy();
    expect(mocks.auth.signUp).not.toHaveBeenCalled();
  });
  it("routes login using backend membership, ignoring submitted role", async () => {
    mocks.session.mockResolvedValue({role:"LAB_TECHNICIAN"});
    await expect(loginAction(form({email:"tech@example.org",password:"valid",role:"ORG_ADMIN"}))).rejects.toThrow("REDIRECT:/lab");
  });
  it("explains email verification errors", async () => {
    mocks.auth.signInWithPassword.mockResolvedValue({error:{code:"email_not_confirmed"}});
    expect((await loginAction(form({email:"a@example.org",password:"valid"})))?.error).toContain("Verify your email");
  });
  it("reports backend outages without claiming onboarding is required", async () => {
    mocks.session.mockRejectedValue(new Error("connection refused"));
    await expect(loginAction(form({email:"a@example.org",password:"valid"}))).rejects.toThrow("REDIRECT:/account?notice=organization_unavailable");
  });
  it("logs out globally and does not conceal logout failure", async () => {
    await expect(logoutAction()).rejects.toThrow("REDIRECT:/login");
    expect(mocks.auth.signOut).toHaveBeenCalledWith({scope:"global"});
    mocks.auth.signOut.mockResolvedValue({error:{code:"unexpected_failure"}});
    await expect(logoutAction()).rejects.toThrow("logout_failed");
  });
  it("sends recovery without revealing account existence", async () => {
    expect((await requestPasswordReset(form({email:"a@example.org"}))).message).toContain("If the account exists");
    expect(mocks.auth.resetPasswordForEmail.mock.calls[0]![1].redirectTo).toContain("/auth/callback?next=/account/password");
  });
  it("requires a verified server user for password updates", async () => {
    mocks.auth.getUser.mockResolvedValue({data:{user:null}});
    expect((await changePassword(form({password:"new-strong-password"}))).error).toBeTruthy();
    expect(mocks.auth.updateUser).not.toHaveBeenCalled();
  });
  it("updates passwords through Auth and revokes sessions", async () => {
    mocks.auth.getUser.mockResolvedValue({data:{user:{id:"user"}}});
    expect((await changePassword(form({password:"new-strong-password"}))).message).toContain("Password updated");
    expect(mocks.auth.signOut).toHaveBeenCalledWith({scope:"global"});
  });
  it("resends signup verification", async () => {
    expect((await resendVerification(form({email:"a@example.org"}))).message).toContain("If your account");
    expect(mocks.auth.resend.mock.calls[0]![0].type).toBe("signup");
  });
  it("only verifies the email link on explicit submission, not on load", async () => {
    await expect(confirmEmailAction(form({token_hash:"tok",type:"signup"}))).rejects.toThrow("REDIRECT:/onboarding");
    expect(mocks.auth.verifyOtp).toHaveBeenCalledWith({token_hash:"tok",type:"signup"});
  });
  it("sends a recovery confirmation to the password page", async () => {
    await expect(confirmEmailAction(form({token_hash:"tok",type:"recovery"}))).rejects.toThrow("REDIRECT:/account/password");
  });
  it("redirects to login with an error when the link is invalid or already used", async () => {
    mocks.auth.verifyOtp.mockResolvedValue({error:{code:"otp_expired"}});
    await expect(confirmEmailAction(form({token_hash:"tok",type:"signup"}))).rejects.toThrow("REDIRECT:/login?error=invalid_link");
  });
  it("rejects a confirmation submission missing required fields", async () => {
    await expect(confirmEmailAction(form({type:"signup"}))).rejects.toThrow("REDIRECT:/login?error=invalid_link");
    expect(mocks.auth.verifyOtp).not.toHaveBeenCalled();
  });
  it("only exchanges the PKCE code on explicit submission, not on load", async () => {
    await expect(exchangeCodeAction(form({code:"c",next:"/onboarding"}))).rejects.toThrow("REDIRECT:/onboarding");
    expect(mocks.auth.exchangeCodeForSession).toHaveBeenCalledWith("c");
  });
  it("sends a password-reset code exchange to the password page", async () => {
    await expect(exchangeCodeAction(form({code:"c",next:"/account/password"}))).rejects.toThrow("REDIRECT:/account/password");
  });
  it("redirects to login with an error when the code is invalid or already used", async () => {
    mocks.auth.exchangeCodeForSession.mockResolvedValue({error:{code:"otp_expired"}});
    await expect(exchangeCodeAction(form({code:"c",next:"/onboarding"}))).rejects.toThrow("REDIRECT:/login?error=invalid_link");
  });
  it("rejects a code-exchange submission missing required fields", async () => {
    await expect(exchangeCodeAction(form({next:"/onboarding"}))).rejects.toThrow("REDIRECT:/login?error=invalid_link");
    expect(mocks.auth.exchangeCodeForSession).not.toHaveBeenCalled();
  });
});
