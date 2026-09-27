"use client";

/**
 * Browser API client. Used ONLY from Client Components / event handlers.
 * Server Components must use `server.ts` instead so cookies stay server-side.
 */
import { ApiError } from "./errors";
import { getPublicEnv } from "@/lib/env/env";

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  timeoutMs?: number;
  idempotencyKey?: string;
}

function newRequestId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export async function apiClient<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const base = getPublicEnv().NEXT_PUBLIC_API_BASE_URL;
  const requestId = newRequestId();
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? 15000);

  try {
    const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
    const res = await fetch(`${base}${endpoint}`, {
      ...options,
      signal: controller.signal,
      headers: {
        Accept: "application/json",
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        "X-Client-Platform": "Dr.Retina-Web",
        "X-Request-Id": requestId,
        ...(options.idempotencyKey ? { "Idempotency-Key": options.idempotencyKey } : {}),
        ...options.headers,
      },
      body: isFormData
        ? (options.body as FormData)
        : options.body === undefined
          ? undefined
          : JSON.stringify(options.body),
      credentials: "include",
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const message =
        typeof body?.message === "string" ? body.message : `Request failed (${res.status})`;
      throw new ApiError({ message, status: res.status, requestId });
    }
    return (await res.json()) as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new ApiError({ message: "Request timed out. Please try again.", status: 408, requestId });
    }
    throw new ApiError({
      message: "Network error. Check your connection and try again.",
      status: 0,
      requestId,
    });
  } finally {
    clearTimeout(timeout);
  }
}
