import { test, expect } from "@playwright/test";
test("landing loads with hero and interactive viewer", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: /Diabetic Retinopathy/i })).toBeVisible();
  await expect(page.getByRole("link", { name: /Login to Screening Portal/i })).toBeVisible();
  await page.getByRole("button", { name: "Optic Disc Assessment details" }).click();
  await expect(page.getByRole("heading", { name: "Optic Disc Assessment", exact: true })).toBeVisible();
});
test("organization entry leads to account-based sign-in", async ({ page }) => {
  await page.goto("/select-org");
  await expect(page.getByRole("heading", { name: /Your organization workspace/i })).toBeVisible();
  await page.getByRole("link", { name: /Continue to Login/i }).click();
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: /Sign In to Dr.Retina/i })).toBeVisible();
  await page.getByRole("link", { name: /Forgot password/i }).click();
  await expect(page.getByRole("heading", { name: /Recover your account/i })).toBeVisible();
});
test("unauthenticated and forged prototype cookies cannot open portals", async ({ page, context }) => {
  await context.addCookies([{ name:"dr_retina_session", value:Buffer.from(JSON.stringify({
    userId:"forged-user",email:"attacker@example.org",role:"ORG_ADMIN",orgId:"forged-org",
  })).toString("base64url"), domain:"localhost", path:"/" }]);
  for (const route of ["/doctor","/admin","/lab","/account","/account/password"]) {
    await page.goto(route);
    await expect(page).toHaveURL(/\/login/);
  }
});
test("expired auth links explain recovery and registration checks password confirmation", async ({ page }) => {
  await page.goto("/auth/confirm?type=not_allowed&token_hash=invalid");
  await expect(page.getByRole("alert")).toContainText("expired");
  await page.goto("/onboarding");
  await page.getByLabel("Email", {exact:true}).fill("test@example.org");
  await page.getByLabel("New password", {exact:true}).fill("example-password-123");
  await page.getByLabel("Confirm password", {exact:true}).fill("different-password-123");
  await page.getByRole("button", {name:"Verify email",exact:true}).click();
  await expect(page.getByRole("alert")).toContainText("Passwords do not match");
});
test("API rejects anonymous reads and cross-origin writes", async ({ request }) => {
  expect((await request.get("/api/backend/patients")).status()).toBe(401);
  expect((await request.post("/api/backend/patients", {
    headers:{ Origin:"https://untrusted.example" }, data:{},
  })).status()).toBe(403);
});
test("onboarding is accessible without sample organizations", async ({ page }) => {
  await page.goto("/onboarding");
  await expect(page.getByRole("heading", { name:/Create your administrator account/i })).toBeVisible();
  await expect(page.getByLabel("Email", { exact:true })).toBeVisible();
});
test("mobile landing has no horizontal overflow", async ({ page }) => {
  await page.setViewportSize({ width:375,height:812 });
  await page.goto("/");
  await page.getByRole("button", { name:"Optic Disc Assessment details" }).click();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
