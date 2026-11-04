"use client";
import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import AuthForm from "@/components/AuthForm";
import Dashboard from "@/components/Dashboard";
import { configured, supabase } from "@/lib/supabase";

export default function Home() {
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    (window as unknown as { __piqReady?: boolean }).__piqReady = true;
    supabase.auth.getSession().then(({ data }) => { setSession(data.session); setReady(true); });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => sub.subscription.unsubscribe();
  }, []);

  return (
    <main className="wrap">
      <header className="top">
        <div className="brand"><span className="mark">IQ</span><span>Profile<b>IQ</b></span></div>
        <span id="header-slot" style={{ display: "contents" }}>{!session && <span className="pill" style={{ borderColor: "var(--amber)", color: "var(--amber)", background: "transparent" }}>AI Powered</span>}</span>
      </header>
      {!configured && <div className="err">The app is not configured yet (missing Supabase settings).</div>}
      {!ready ? <p className="muted">Loading…</p> : session ? <Dashboard /> : (<>
        <h1>Land the <em>job.</em><br />Not the rejection.</h1>
        <p className="muted" style={{ marginBottom: 20 }}>ProfileIQ scores your resume against any job description, shows every gap, and rewrites it to pass ATS — in under 30 seconds.</p>
        <AuthForm />
      </>)}
    </main>
  );
}
