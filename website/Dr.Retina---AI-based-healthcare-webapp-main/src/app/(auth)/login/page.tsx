import * as React from "react";
import { LoginForm } from "@/features/auth/LoginForm";
import { ResendVerification } from "@/features/auth/ResendVerification";

export const metadata = { title: "Sign In | Dr.Retina" };

export default function LoginPage() {
  return (
    <React.Suspense fallback={<div className="p-8 text-center text-sm text-slate-500" aria-busy="true">Loading sign-in...</div>}>
      <LoginForm />
      <div className="max-w-xl mx-auto px-6 pb-8"><ResendVerification /></div>
    </React.Suspense>
  );
}
