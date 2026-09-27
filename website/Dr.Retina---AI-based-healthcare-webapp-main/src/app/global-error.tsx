"use client";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <html lang="en">
      <body className="bg-slate-50 text-slate-900 font-sans antialiased">
        <div className="min-h-screen flex items-center justify-center px-4">
          <div role="alert" className="text-center">
            <h1 className="text-2xl font-extrabold">Application error</h1>
            <p className="text-sm text-slate-500 mt-2">Please reload the page. No diagnostic details are shown here by design.</p>
            <button onClick={reset} className="mt-6 px-6 py-3 rounded-full text-sm font-semibold text-white bg-brand-600 hover:bg-brand-700">
              Reload
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
