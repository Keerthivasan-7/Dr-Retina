"use client";
export function PrintButton() {
  return <button onClick={() => window.print()} className="print:hidden rounded-xl bg-brand-600 text-white px-5 py-3">Print / save PDF</button>;
}
