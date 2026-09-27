export function authErrorMessage(error: { code?: string }, fallback: string): string {
  switch (error.code) {
    case "email_not_confirmed": return "Verify your email before signing in. You can request another verification email below.";
    case "invalid_credentials": return "Email or password is incorrect.";
    case "over_request_rate_limit":
    case "over_email_send_rate_limit": return "Too many attempts. Please wait a few minutes and try again.";
    case "weak_password": return "Choose a stronger password with at least 12 characters.";
    case "same_password": return "Choose a password different from your current password.";
    default: return fallback;
  }
}
