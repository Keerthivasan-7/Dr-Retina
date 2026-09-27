/** Standardized API error — never silently swallowed, never leaks internals to UI. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId: string;
  readonly retryable: boolean;

  constructor(opts: {
    message: string;
    status: number;
    code?: string;
    requestId?: string;
  }) {
    super(opts.message);
    this.name = "ApiError";
    this.status = opts.status;
    this.code = opts.code ?? `HTTP_${opts.status}`;
    this.requestId = opts.requestId ?? crypto.randomUUID();
    this.retryable = opts.status === 408 || opts.status === 429 || opts.status >= 500;
  }
}

export function toUserMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return "Your session has expired. Please sign in again.";
    if (error.status === 403) return "You do not have permission to perform this action.";
    if (error.status === 404) return "The requested record was not found.";
    if (error.status >= 500) return "The service is temporarily unavailable. Please try again.";
    return error.message;
  }
  return "An unexpected error occurred. Please try again.";
}
