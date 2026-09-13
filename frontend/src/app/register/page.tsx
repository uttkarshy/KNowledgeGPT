"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { apiJson, ApiError } from "@/lib/api-client";

// Mirrors the backend's _validate_password_strength rules exactly, so the
// user sees the same requirement in the form instead of discovering it only
// after a 422 comes back from the API.
const registerSchema = z.object({
  full_name: z.string().max(255).optional(),
  email: z.string().email("Enter a valid email address"),
  password: z
    .string()
    .min(10, "At least 10 characters")
    .regex(/[A-Z]/, "At least one uppercase letter")
    .regex(/[a-z]/, "At least one lowercase letter")
    .regex(/\d/, "At least one digit")
    .regex(/[^\w\s]/, "At least one special character")
    .refine(v => new TextEncoder().encode(v).length <= 72, "Maximum 72 UTF-8 bytes"),
});

type RegisterForm = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterForm>({ resolver: zodResolver(registerSchema) });

  const onSubmit = async (data: RegisterForm) => {
    setServerError(null);
    setIsSubmitting(true);
    try {
      await apiJson("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(data),
        skipAuth: true,
      });
      setSuccess(true);
      setTimeout(() => router.push("/login"), 2000);
    } catch (e) {
      setServerError(e instanceof ApiError ? e.detail : "Something went wrong. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  if (success) {
    return (
      <main className="min-h-screen flex items-center justify-center bg-mist-50 dark:bg-ink-950 px-4">
        <div className="max-w-sm text-center">
          <h1 className="font-display text-xl text-ink-900 dark:text-mist-50">Account created</h1>
          <p className="mt-2 text-sm text-ink-500">
            Your account is ready. If email verification is enabled, check your inbox. Redirecting you to sign in…
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen flex items-center justify-center bg-mist-50 dark:bg-ink-950 px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <h1 className="font-display text-2xl font-medium text-ink-900 dark:text-mist-50">
            Create your workspace
          </h1>
          <p className="mt-1 text-sm text-ink-500">Start chatting with your own documents</p>
        </div>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="rounded-lg border border-mist-200 bg-white p-6 shadow-sm dark:border-ink-700 dark:bg-ink-900"
        >
          {serverError && (
            <div className="mb-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {serverError}
            </div>
          )}

          <label className="block text-sm font-medium text-ink-700 dark:text-mist-100">
            Full name
            <input
              type="text"
              {...register("full_name")}
              className="mt-1 w-full rounded-md border border-mist-200 bg-transparent px-3 py-2 text-sm outline-none focus-visible:border-stamp-teal dark:border-ink-700"
            />
          </label>

          <label className="mt-4 block text-sm font-medium text-ink-700 dark:text-mist-100">
            Email
            <input
              type="email"
              autoComplete="email"
              {...register("email")}
              className="mt-1 w-full rounded-md border border-mist-200 bg-transparent px-3 py-2 text-sm outline-none focus-visible:border-stamp-teal dark:border-ink-700"
            />
          </label>
          {errors.email && <p className="mt-1 text-xs text-danger">{errors.email.message}</p>}

          <label className="mt-4 block text-sm font-medium text-ink-700 dark:text-mist-100">
            Password
            <input
              type="password"
              autoComplete="new-password"
              {...register("password")}
              className="mt-1 w-full rounded-md border border-mist-200 bg-transparent px-3 py-2 text-sm outline-none focus-visible:border-stamp-teal dark:border-ink-700"
            />
          </label>
          {errors.password && <p className="mt-1 text-xs text-danger">{errors.password.message}</p>}
          <p className="mt-1 text-xs text-ink-500">
            At least 10 characters, with uppercase, lowercase, a digit, and a symbol.
          </p>

          <button
            type="submit"
            disabled={isSubmitting}
            className="mt-5 w-full rounded-md bg-stamp-teal py-2 text-sm font-medium text-white transition hover:bg-stamp-tealDark disabled:opacity-60"
          >
            {isSubmitting ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-500">
          Already have an account?{" "}
          <Link href="/login" className="text-stamp-teal hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </main>
  );
}
