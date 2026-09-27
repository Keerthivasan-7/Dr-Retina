import { NextResponse } from "next/server";

/** On-demand revalidation hook for safe (non-patient) content. */
export async function POST(request: Request) {
  const secret = process.env.API_REVALIDATE_SECRET;
  if (!secret) return NextResponse.json({ message: "Revalidation not configured" }, { status: 501 });
  const body = await request.json().catch(() => ({}));
  if (body.secret !== secret) return NextResponse.json({ message: "Forbidden" }, { status: 403 });
  return NextResponse.json({ revalidated: true });
}
