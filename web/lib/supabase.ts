import { createClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const anon = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

// Only the public (anon) key ever reaches the browser; row-level security protects the data.
export const supabase = createClient(url || "http://localhost", anon || "missing", {
  auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
});
export const configured = Boolean(url && anon);
