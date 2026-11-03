"use client";
import { useState } from "react";
import { supabase } from "@/lib/supabase";
import { isValidEmail, normalizeIndianMobile } from "@/lib/validate";

type Mode = "login" | "signup" | "forgot";

export default function AuthForm() {
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [mobile, setMobile] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const origin = typeof window !== "undefined" ? window.location.origin : "";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setNotice("");
    const em = email.trim();
    if (!isValidEmail(em)) return setError("Enter a valid email address.");
    setBusy(true);
    try {
      if (mode === "forgot") {
        const { error } = await supabase.auth.resetPasswordForEmail(em, { redirectTo: origin });
        if (error) throw error;
        setNotice("If that email has an account, a reset link is on its way.");
      } else if (mode === "login") {
        const { error } = await supabase.auth.signInWithPassword({ email: em, password });
        if (error) throw error;
      } else {
        const nm = name.trim();
        if (nm.length < 2) return setError("Enter your full name.");
        const mob = normalizeIndianMobile(mobile);
        if (!mob) return setError("Enter a valid 10-digit Indian mobile number.");
        if (password.length < 6) return setError("Password must be at least 6 characters.");
        const { data, error } = await supabase.auth.signUp({
          email: em, password, options: { data: { full_name: nm, mobile: mob }, emailRedirectTo: origin },
        });
        if (error) throw error;
        if (data.user && (data.user.identities?.length ?? 0) === 0) {
          setError("That email is already registered. Please log in instead.");
        } else if (!data.session) {
          setNotice("Account created. Check your email and click the confirmation link, then log in.");
        }
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong.";
      setError(/invalid login/i.test(msg) ? "Email or password is incorrect." : msg);
    } finally { setBusy(false); }
  }

  return (
    <form className="card" onSubmit={submit} noValidate>
      <h2 style={{ marginTop: 0 }}>{mode === "login" ? "Log in" : mode === "signup" ? "Create your account" : "Reset password"}</h2>
      {mode === "signup" && (<>
        <label htmlFor="name">Full name</label>
        <input id="name" type="text" autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />
        <label htmlFor="mobile">Mobile number</label>
        <input id="mobile" type="tel" inputMode="numeric" autoComplete="tel" placeholder="98765 43210" value={mobile} onChange={(e) => setMobile(e.target.value)} />
      </>)}
      <label htmlFor="email">Email</label>
      <input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
      {mode !== "forgot" && (<>
        <label htmlFor="password">Password</label>
        <input id="password" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={(e) => setPassword(e.target.value)} />
      </>)}
      {error && <div className="err" role="alert">{error}</div>}
      {notice && <div className="ok" role="status">{notice}</div>}
      <div style={{ height: 16 }} />
      <button type="submit" disabled={busy}>{busy ? "Please wait…" : mode === "login" ? "Log in" : mode === "signup" ? "Sign up" : "Send reset link"}</button>
      <div className="row" style={{ marginTop: 10 }}>
        {mode !== "login" && <button type="button" className="link" onClick={() => { setMode("login"); setError(""); setNotice(""); }}>Back to log in</button>}
        {mode === "login" && <button type="button" className="link" onClick={() => { setMode("signup"); setError(""); setNotice(""); }}>Create an account</button>}
        {mode === "login" && <button type="button" className="link" onClick={() => { setMode("forgot"); setError(""); setNotice(""); }}>Forgot password?</button>}
      </div>
    </form>
  );
}
