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

export interface Me { id: string; email: string; full_name?: string | null; is_pro: boolean; scans_left: number | null; pro_expires_at: string | null; cancels_at_period_end?: boolean; has_billing?: boolean; plan_ended_on?: string | null; has_mobile?: boolean }
export interface ScoreResult { score: number; matched: string[]; missing: string[]; suggestions: string[]; scans_left: number | null }

// Remember the last profile so moving between pages shows it instantly while a fresh copy loads.
let meCache: Me | null = null;
export const peekMe = () => meCache;
export const getMe = () => api<Me>("/v1/me").then((m) => (meCache = m));
if (typeof window !== "undefined") supabase.auth.onAuthStateChange((e) => { if (e === "SIGNED_OUT") meCache = null; });
export function scoreResume(file: File, jd: string) {
  const form = new FormData(); form.append("resume", file); form.append("jd", jd);
  return api<ScoreResult>("/v1/score", { method: "POST", body: form });
}

export interface ResumeData {
  name?: string; title?: string; contact?: string; summary?: string;
  [k: string]: unknown;
}
export interface RewriteResult { data: ResumeData; after_score: number; after_matched: string[]; after_missing: string[] }
export interface FresherProfile {
  full_name: string; email: string; phone: string; degree: string; institute: string;
  university: string; year_of_passing: string; key_skills: string;
  projects: { name: string; description: string }[];
  certifications: { name: string }[];
}

export const getTemplates = () => api<{ templates: string[] }>("/v1/templates");
export function rewriteResume(file: File, jd: string) {
  const form = new FormData(); form.append("resume", file); form.append("jd", jd);
  return api<RewriteResult>("/v1/rewrite", { method: "POST", body: form });
}
export const buildFresher = (profile: FresherProfile, jd: string) =>
  api<{ data: ResumeData }>("/v1/fresher", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ profile, jd }),
  });
export const previewResume = (data: ResumeData, template: string) =>
  api<{ html: string }>("/v1/resume/preview", {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ data, template, format: "pdf" }),
  });

export async function downloadResume(data: ResumeData, template: string, format: "pdf" | "docx") {
  const { data: sess } = await supabase.auth.getSession();
  let res: Response;
  try {
    res = await fetch(`${API_URL}/v1/resume/file`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${sess.session?.access_token ?? ""}` },
      body: JSON.stringify({ data, template, format }),
    });
  } catch { throw new ApiError("We couldn't reach the server. Check your connection and try again.", "network", 0); }
  if (!res.ok) {
    let b: { message?: string; ref?: string } = {};
    try { b = await res.json(); } catch { /* ignore */ }
    throw new ApiError(b.message ?? "Download failed. Please try again.", b.ref ?? `http-${res.status}`, res.status);
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url; a.download = `ProfileIQ_Resume.${format}`; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export interface Subscribe { subscription_id: string; key_id: string; email: string; contact: string }
const post = <T>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });
export const startSubscription = (mobile?: string) => post<Subscribe>("/v1/billing/subscribe", { mobile: mobile || null });
export const confirmSubscription = (subscription_id: string) => post<{ status: "paid" | "pending" | "not_paid" }>("/v1/billing/confirm", { subscription_id });
export const cancelSubscription = () => post<{ ok: boolean }>("/v1/billing/cancel");

export interface Invoice { id: number; invoice_number: string; issued_at: string; amount_paise: number; currency: string; payment_method: string | null; emailed_at: string | null }
export const listInvoices = () => api<{ invoices: Invoice[] }>("/v1/invoices");
export const emailInvoice = (id: number) => post<{ sent_to: string }>(`/v1/invoices/${id}/email`);
export const sendSupport = (type: string, message: string) => post<{ ok: boolean }>("/v1/support", { type, message });
