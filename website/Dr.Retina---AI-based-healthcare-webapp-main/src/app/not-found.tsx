import Link from "next/link";

export default function NotFound() {
  return (
    <div className="min-h-[60vh] flex items-center justify-center px-4">
      <div className="text-center">
        <h1 className="text-4xl font-extrabold text-slate-900">Page not found</h1>
        <p className="text-sm text-slate-500 mt-2">The page you requested does not exist.</p>
        <Link href="/" className="mt-6 inline-block px-6 py-3 rounded-full text-sm font-semibold text-white bg-brand-600 hover:bg-brand-700">
          Back to home
        </Link>
      </div>
    </div>
  );
}
