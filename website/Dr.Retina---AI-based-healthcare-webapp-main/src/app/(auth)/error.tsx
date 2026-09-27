"use client";
export default function AuthError({ reset }: { reset: () => void }) {
  return <div role="alert" className="max-w-lg mx-auto my-12 rounded-3xl border bg-white p-8 shadow-card">
    <h1 className="text-xl font-bold">We could not load your account</h1>
    <p className="my-4 text-sm text-slate-600">The account or organization service is temporarily unavailable. Please try again. Your clinical access remains protected.</p>
    <button onClick={reset} className="rounded-xl bg-brand-600 px-4 py-3 text-white">Try again</button>
  </div>;
}
