"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getMe, peekMe, type Me } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import { Invoices, Subscription, Support } from "./Account";
import ProfileMenu from "./ProfileMenu";
import SiteFooter from "./SiteFooter";

// Separate pages for "Manage plan" (/account) and "Support" (/support). Both need a signed-in user.
export default function AccountPage({ kind }: { kind: "account" | "support" }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(peekMe());
  const [error, setError] = useState("");
  const [ready, setReady] = useState(peekMe() !== null);

  useEffect(() => {
    let alive = true;
    supabase.auth.getSession().then(({ data }) => {
      if (!alive) return;
      if (!data.session) { router.replace("/"); return; }
      setReady(true);
      getMe().then((m) => alive && setMe(m)).catch(() => alive && setError("We couldn't load your account. Please go back and try again."));
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => { if (!s) router.replace("/"); });
    return () => { alive = false; sub.subscription.unsubscribe(); };
  }, [router]);

  return (
    <main className="legalpage">
      <header className="legal-top">
        <Link href="/" className="brand" aria-label="ProfileIQ home"><span className="mark">IQ</span><span>Profile<b>IQ</b></span></Link>
        <div className="row" style={{ flex: "0 0 auto", gap: 10 }}>
          <Link href="/" className="backbtn" style={{ margin: 0 }}>← Back to home</Link>
          {me && <ProfileMenu me={me} onSignOut={() => supabase.auth.signOut()} />}
        </div>
      </header>
      <section className="acct-page">
        <h1 className="acct-title">{kind === "account" ? "Manage plan" : "Support"}</h1>
        {error && <div className="err" role="alert">{error}</div>}
        {!ready || (!me && !error) ? <p className="muted">Loading…</p> : kind === "account" ? (
          <><Subscription me={me} onChanged={setMe} /><Invoices /></>
        ) : (
          <Support me={me} onClose={() => router.push("/")} />
        )}
      </section>
      <SiteFooter />
    </main>
  );
}
