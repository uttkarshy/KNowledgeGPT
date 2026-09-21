"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { apiJson, setTokens, ApiError } from "@/lib/api-client";
import { AuthShell } from "@/components/auth-shell";

const loginSchema = z.object({
  email: z.string().email("Enter a valid email address"),
  password: z.string().min(1, "Enter your password"),
});

type LoginForm = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const router = useRouter();
  const [serverError, setServerError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({ resolver: zodResolver(loginSchema) });

  const onSubmit = async (data: LoginForm) => {
    setServerError(null);
    setIsSubmitting(true);
    try {
      const result = await apiJson<{ access_token: string; refresh_token: string }>(
        "/api/auth/login",
        { method: "POST", body: JSON.stringify(data), skipAuth: true }
      );
      setTokens(result.access_token, result.refresh_token);
      router.push("/dashboard");
    } catch (e) {
      setServerError(e instanceof ApiError ? e.detail : "Something went wrong. Try again.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthShell>
      <div>
        <div className="mb-8">
          <p className="text-sm font-semibold text-stamp-teal">Welcome back</p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-[-0.03em] text-ink-950 dark:text-white">
            Sign in to your workspace
          </h1>
          <p className="mt-2 text-sm leading-6 text-ink-500">Continue asking questions across your documents.</p>
        </div>

        <form
          onSubmit={handleSubmit(onSubmit)}
          className="surface-card p-6 sm:p-7"
        >
          {serverError && (
            <div className="mb-4 rounded-md border border-danger/30 bg-danger/10 px-3 py-2 text-sm text-danger">
              {serverError}
            </div>
          )}

          <label className="block text-sm font-medium text-ink-700 dark:text-mist-100">
            Email
            <input
              type="email"
              autoComplete="email"
              {...register("email")}
              className="field-control mt-2"
            />
          </label>
          {errors.email && <p className="mt-1 text-xs text-danger">{errors.email.message}</p>}

          <label className="mt-4 block text-sm font-medium text-ink-700 dark:text-mist-100">
            Password
            <input
              type="password"
              autoComplete="current-password"
              {...register("password")}
              className="field-control mt-2"
            />
          </label>
          {errors.password && <p className="mt-1 text-xs text-danger">{errors.password.message}</p>}

          <div className="mt-2 flex justify-end">
            <Link href="/forgot-password" className="text-xs text-stamp-teal hover:underline">
              Forgot password?
            </Link>
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="primary-button mt-6 w-full"
          >
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="mt-6 text-center text-sm text-ink-500">
          Don&apos;t have an account?{" "}
          <Link href="/register" className="text-stamp-teal hover:underline">
            Create one
          </Link>
        </p>
      </div>
    </AuthShell>
  );
}
