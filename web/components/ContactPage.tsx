"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { supabase } from "@/lib/supabase";
import SiteFooter from "./SiteFooter";

const EMAIL = "support@profileiq.co.in";

export default function ContactPage() {
  const [signedIn, setSignedIn] = useState(false);
  const [copied, setCopied] = useState(false);
  useEffect(() => { supabase.auth.getSession().then(({ data }) => setSignedIn(!!data.session)); }, []);

  async function copy() {
    try { await navigator.clipboard.writeText(EMAIL); setCopied(true); setTimeout(() => setCopied(false), 2000); }
    catch { /* clipboard blocked: the address is shown on screen to select */ }
  }

  return (
    <main className="legalpage">
      <header className="legal-top">
        <Link href="/" className="brand" aria-label="ProfileIQ home"><span className="mark">IQ</span><span>Profile<b>IQ</b></span></Link>
        <Link href="/" className="backbtn">← Back to home</Link>
      </header>
      <section className="acct-page">
        <h1 className="acct-title">Contact Us</h1>
        <p className="muted" style={{ marginBottom: 16 }}>Questions, billing help or feedback? We usually reply within one working day.</p>
        {signedIn && (
          <div className="card" style={{ marginBottom: 14 }}>
            <strong>Send us a message</strong>
            <p className="muted" style={{ margin: "6px 0 12px" }}>The quickest way: it reaches us with your account details attached.</p>
            <Link href="/support" className="btn" style={{ display: "block" }}>Open the support form</Link>
          </div>
        )}
        <div className="card">
          <strong>Email</strong>
          <p style={{ margin: "8px 0 12px", fontSize: 18, fontWeight: 700, overflowWrap: "anywhere", userSelect: "all" }}>{EMAIL}</p>
          <div className="row">
            <a className="btn" href={`mailto:${EMAIL}`}>Open my email app</a>
            <button className="ghost" onClick={copy} aria-live="polite">{copied ? "Copied ✓" : "Copy address"}</button>
          </div>
          <p className="muted" style={{ fontSize: 13, marginTop: 12 }}>If nothing opens when you tap the email button, copy the address and write to us from any email app.</p>
        </div>
      </section>
      <SiteFooter />
    </main>
  );
}
