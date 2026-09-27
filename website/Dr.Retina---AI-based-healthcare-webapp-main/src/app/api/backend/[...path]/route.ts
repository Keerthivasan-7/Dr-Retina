import { NextRequest } from "next/server";
import { backendToken } from "@/lib/api/server";
import { readBoundedBody, BodyTooLarge } from "@/lib/api/body";
async function forward(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (path.some(segment => !/^[a-zA-Z0-9_-]+$/.test(segment)))
    return Response.json({ message: "Invalid API path" }, { status: 400 });
  if (!["GET", "HEAD"].includes(request.method) &&
      request.headers.get("origin") !== (process.env.APP_URL ?? request.nextUrl.origin))
    return Response.json({ message: "Invalid request origin" }, { status: 403 });
  try {
    const token = await backendToken();
    if (!token) return Response.json({ message: "Sign in to continue" }, { status: 401 });
    const headers = new Headers({ Authorization: `Bearer ${token}` });
    for (const name of ["content-type", "idempotency-key"]) {
      const value = request.headers.get(name); if (value) headers.set(name, value);
    }
    const body = ["GET", "HEAD"].includes(request.method) ? undefined : await readBoundedBody(request);
    if (body && body.byteLength > 27 * 1024 * 1024)
      return Response.json({ message: "Upload exceeds the limit" }, { status: 413 });
    const base = process.env.API_INTERNAL_BASE_URL ?? "http://localhost:8000/api/v1";
    const response = await fetch(`${base}/${path.join("/")}${request.nextUrl.search}`, {
      method: request.method, headers, body, cache: "no-store", signal: AbortSignal.timeout(65000),
    });
    return new Response(response.body, { status: response.status, headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/json",
      "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
    } });
  } catch (error) {
    if (error instanceof BodyTooLarge) return Response.json({ message: "Upload exceeds the limit" }, { status: 413 });
    return Response.json({ message: "The clinical service is unavailable. Please try again." }, { status: 503 });
  }
}
export { forward as GET, forward as POST, forward as PATCH, forward as DELETE };
