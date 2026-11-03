import { supabase } from "./supabase";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  status: number; ref: string;
  constructor(message: string, ref: string, status: number) { super(message); this.status = status; this.ref = ref; }
}

async function token(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? "";
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init, headers: { ...(init.headers ?? {}), Authorization: `Bearer ${await token()}` },
    });
  } catch {
    throw new ApiError("We couldn't reach the server. Check your connection and try again.", "network", 0);
  }
  if (!res.ok) {
    let body: { message?: string; ref?: string } = {};
    try { body = await res.json(); } catch { /* not JSON */ }
    throw new ApiError(body.message ?? "Something went wrong. Please try again.", body.ref ?? `http-${res.status}`, res.status);
  }
  return res.json() as Promise<T>;
}

export interface Me { id: string; email: string; full_name?: string | null; is_pro: boolean; scans_left: number | null; pro_expires_at: string | null }
export interface ScoreResult { score: number; matched: string[]; missing: string[]; suggestions: string[]; scans_left: number | null }

export const getMe = () => api<Me>("/v1/me");
export function scoreResume(file: File, jd: string) {
  const form = new FormData(); form.append("resume", file); form.append("jd", jd);
  return api<ScoreResult>("/v1/score", { method: "POST", body: form });
}
