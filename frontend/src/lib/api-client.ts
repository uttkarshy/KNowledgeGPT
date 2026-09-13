/**
 * API client. All backend calls go through here so token attachment,
 * refresh-on-401, and the base URL are handled in exactly one place.
 *
 * Tokens are kept in memory + localStorage (access token short-lived,
 * refresh token longer-lived) rather than cookies, since the backend is a
 * separate origin in dev and this avoids CSRF-token plumbing for a
 * bearer-token API. If this is deployed same-origin behind a reverse proxy,
 * consider moving to httpOnly cookies instead — see the security notes in
 * the backend's auth increment for the tradeoffs.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const ACCESS_TOKEN_KEY = "kgpt_access_token";
const REFRESH_TOKEN_KEY = "kgpt_refresh_token";

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  // Coalesce concurrent 401s into a single refresh call rather than firing
  // one refresh request per in-flight request.
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE}/api/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })
      .then(async (res) => {
        if (!res.ok) {
          clearTokens();
          return null;
        }
        const data = await res.json();
        setTokens(data.access_token, data.refresh_token);
        return data.access_token as string;
      })
      .finally(() => {
        refreshPromise = null;
      });
  }
  return refreshPromise;
}

interface RequestOptions extends RequestInit {
  skipAuth?: boolean;
}

export async function apiFetch(path: string, options: RequestOptions = {}): Promise<Response> {
  const { skipAuth, headers, ...rest } = options;
  const accessToken = skipAuth ? null : getAccessToken();

  const doFetch = (token: string | null) =>
    fetch(`${API_BASE}${path}`, {
      credentials: "include",
      ...rest,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
    });

  let response = await doFetch(accessToken);

  if (response.status === 401 && !skipAuth) {
    const newToken = await refreshAccessToken();
    if (newToken) {
      response = await doFetch(newToken);
    }
  }

  return response;
}

export async function apiJson<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await apiFetch(path, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = Array.isArray(body.detail) ? body.detail.map((e: { message?: string; msg?: string }) => e.message || e.msg || "Invalid input").join("; ") : String(body.detail || detail);
    } catch {
      /* response body wasn't JSON */
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export { API_BASE };
