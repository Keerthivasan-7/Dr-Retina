/** Live portals never substitute simulated clinical predictions or sample patients. */
export function isDemoMode(): boolean { return false; }
export function getPublicEnv() {
  return { NEXT_PUBLIC_API_BASE_URL: "/api/backend", NEXT_PUBLIC_DEMO_MODE: false };
}
