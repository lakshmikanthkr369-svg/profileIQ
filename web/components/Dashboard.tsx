"use client";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { ApiError, confirmSubscription, getMe, scoreResume, type Me, type ScoreResult } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import Rewrite from "./Rewrite";
import Upgrade from "./Upgrade";
import { Invoices, Subscription, Support } from "./Account";
import ProfileMenu from "./ProfileMenu";
import { PENDING_KEY, isCheckoutOpen, onCheckoutChange, pageIsLocked, unlockPage } from "@/lib/checkout";

const MAX_MB = 10;

export default function Dashboard() {
  const [me, setMe] = useState<Me | null>(null);
  const [meError, setMeError] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [jd, setJd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; ref: string } | null>(null);
  const [result, setResult] = useState<ScoreResult | null>(null);
  const [level, setLevel] = useState<"existing" | "fresher">("existing");
  const picker = useRef<HTMLInputElement>(null);
  const [panel, setPanel] = useState<"" | "billing" | "support">("");
  const [payNote, setPayNote] = useState("");

  // Scroll-lock guard. A fresh load can't have a payment running, so clear everything. After that, keep the
  // page scrollable: if nothing of ours has checkout open but the page is locked, unlock it; and if checkout
  // seems stuck (e.g. back from a UPI app) offer a one-tap way out.
  const [stuck, setStuck] = useState(false);
  const [slot, setSlot] = useState<HTMLElement | null>(null);
  useEffect(() => { setSlot(document.getElementById("header-slot")); }, []);
  useEffect(() => {
    unlockPage(true);
    const guard = setInterval(() => { if (!isCheckoutOpen() && pageIsLocked()) unlockPage(false); }, 600);
    let timer: ReturnType<typeof setTimeout> | undefined;
    const off = onCheckoutChange((o) => { clearTimeout(timer); setStuck(false); if (o) timer = setTimeout(() => setStuck(true), 25000); });
    const back = () => { if (!isCheckoutOpen()) unlockPage(false); };
    const vis = () => { if (document.visibilityState === "visible") { back(); if (isCheckoutOpen()) setTimeout(() => setStuck(true), 4000); } };
    window.addEventListener("pageshow", back);
    document.addEventListener("visibilitychange", vis);
    return () => { clearInterval(guard); clearTimeout(timer); off(); window.removeEventListener("pageshow", back); document.removeEventListener("visibilitychange", vis); };
  }, []);

  useEffect(() => {
    getMe().then(setMe).catch((e: ApiError) => setMeError(e.message));
  }, []);

  // If the phone left the page during payment (UPI app hand-off can reload it), finish activating Pro now.
  useEffect(() => {
    if (!me || me.is_pro) return;
    let raw: string | null = null;
    try { raw = localStorage.getItem(PENDING_KEY); } catch { /* storage blocked */ }
    if (!raw) return;
    let pending: { id: string; ts: number } | null = null;
    try { pending = JSON.parse(raw); } catch { /* ignore */ }
    const clear = () => { try { localStorage.removeItem(PENDING_KEY); } catch { /* ignore */ } };
    if (!pending?.id || Date.now() - pending.ts > 30 * 60 * 1000) return clear();
    let stop = false;
    (async () => {
      setPayNote("Checking your payment…");
      for (let i = 0; i < 8 && !stop; i++) {
        const r = await confirmSubscription(pending!.id).catch(() => null);
        if (r?.status === "paid") { clear(); unlockPage(true); setMe(await getMe()); setPayNote("Payment received — you're Pro now. Enjoy!"); return; }
        if (r?.status === "not_paid") { clear(); setPayNote(""); return; }
        await new Promise((res) => setTimeout(res, 2500));
      }
      setPayNote("");
    })();
    return () => { stop = true; };
  }, [me?.is_pro, me === null]); // eslint-disable-line react-hooks/exhaustive-deps

  function choose(f: File | undefined | null) {
    setError(null);
    if (!f) return;
    if (!/\.(pdf|docx?)$/i.test(f.name)) return setError({ message: "Please upload a PDF or Word (.doc, .docx) file.", ref: "bad-type" });
    if (f.size > MAX_MB * 1024 * 1024) return setError({ message: `That file is too large (limit ${MAX_MB} MB).`, ref: "too-large" });
    setFile(f); setResult(null);
  }

  async function analyze() {
    setError(null);
    if (!file) return setError({ message: "Upload your resume to continue.", ref: "no-file" });
    if (!jd.trim()) return setError({ message: "Paste a job description to continue.", ref: "no-jd" });
    setBusy(true);
    try {
      const r = await scoreResume(file, jd);
      setResult(r);
      setMe((m) => (m ? { ...m, scans_left: r.scans_left } : m));
    } catch (e) {
      const err = e as ApiError;
      setError({ message: err.message, ref: err.ref });
    } finally { setBusy(false); }
  }

  const scoreColor = !result ? "" : result.score >= 80 ? "var(--good)" : result.score >= 65 ? "var(--amber)" : "var(--bad)";
  const verdict = !result ? "" : result.score >= 80 ? "Great fit for this position" : result.score >= 65 ? "Good — room to improve" : "Needs work to pass ATS";
  const outOfScans = me && !me.is_pro && (me.scans_left ?? 0) <= 0;

  return (
    <>
      {slot && createPortal(
        <ProfileMenu me={me}
          onManage={() => setPanel(panel === "billing" ? "" : "billing")}
          onSupport={() => setPanel(panel === "support" ? "" : "support")}
          onSignOut={() => supabase.auth.signOut()} />, slot)}
      {stuck && (
        <div className="notice warn" role="status"><strong>Payment screen not closing?</strong>
          If you finished (or cancelled) the payment, tap below to close it and check your plan.
          <div style={{ height: 10 }} />
          <button onClick={async () => { unlockPage(true); setStuck(false); try { setMe(await getMe()); } catch { /* keep current */ } window.scrollTo({ top: 0 }); }}>Close and check my payment</button>
        </div>
      )}
      {payNote && <div className="ok" role="status">{payNote}</div>}
      {me?.is_pro && me.cancels_at_period_end && me.pro_expires_at && (
        <div className="notice warn" role="status"><strong>Your subscription is cancelled</strong>
          You still have Pro until {new Date(me.pro_expires_at).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}. It won&apos;t renew after that.</div>
      )}
      {me && !me.is_pro && me.plan_ended_on && (
        <div className="notice bad" role="status"><strong>Your Pro subscription has ended</strong>
          It ended on {new Date(me.plan_ended_on).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}. Upgrade to get Pro features back.</div>
      )}
      {panel && (
        <button className="backbtn" onClick={() => { setPanel(""); window.scrollTo({ top: 0 }); }}>← Back to home</button>
      )}
      {panel === "billing" && (<><Subscription me={me} onChanged={setMe} /><Invoices /></>)}
      {panel === "support" && <Support me={me} onClose={() => setPanel("")} />}
      {meError && <div className="err" role="alert">{meError}</div>}
      {me && !me.is_pro && (
        <div className="card gopro">
          <div><strong>Go Pro</strong>
          <p className="muted" style={{ margin: "6px 0 0" }}>Unlimited scans, AI rewrite, fresher resume builder, 4 formats and PDF/Word downloads. Cancel any time.</p></div>
          <div><Upgrade me={me} onUpgraded={setMe} /></div>
        </div>
      )}
      {!panel && (<>
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={level === "existing"} className={level === "existing" ? "on" : ""} onClick={() => setLevel("existing")}>I&apos;m experienced</button>
        <button role="tab" aria-selected={level === "fresher"} className={level === "fresher" ? "on" : ""} onClick={() => setLevel("fresher")}>I&apos;m a fresher</button>
      </div>

      {level === "fresher" ? (
        <div className="stack">
          <div className="inputs">
            <div>
              <h2>Job description</h2>
              <textarea value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the full job description here — the more detail, the better the match." />
            </div>
          </div>
          <Rewrite key="fresher" me={me} file={null} jd={jd} mode="fresher" onUpgraded={setMe} />
        </div>
      ) : (
        <div className="workspace">
          <div className="col-in">
      <div className="inputs">
        <div>
            <h2>Your resume</h2>
            {file && (
              <div className="file"><span>{file.name} · {(file.size / 1024).toFixed(0)} KB</span>
                <button className="ghost" onClick={() => { setFile(null); setResult(null); if (picker.current) picker.current.value = ""; }}>Remove</button></div>
            )}
            <label className="drop" htmlFor="resume-input">
              <span className="muted">PDF, DOC or DOCX · up to {MAX_MB} MB</span>
              <span className="btn" role="button">{file ? "Upload a different resume" : "Upload"}</span>
              <input id="resume-input" ref={picker} type="file" accept=".pdf,.doc,.docx" onChange={(e) => choose(e.target.files?.[0])} />
            </label>
          </div>
        <div>
          <h2>Job description</h2>
          <textarea value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the full job description here — the more detail, the better the match." />
        </div>
      </div>

        {error && <div className="err" role="alert">{error.message}<small>Reference: {error.ref}</small></div>}
        {outOfScans && <div className="err">You have used all 3 free scans this month. Upgrade to Pro for unlimited scans — use the Go Pro button above.</div>}
        <button onClick={analyze} aria-busy={busy} disabled={busy || !!outOfScans}>{busy ? "Analyzing…" : "Score my resume"}</button>

          </div>
          <div className="col-out">
        {result ? (
          <div className="card" aria-live="polite">
            <div className="score">
              <div className="muted" style={{ fontSize: 12, letterSpacing: ".1em" }}>ATS SCORE</div>
              <div className="num" style={{ color: scoreColor }}>{result.score}</div>
              <div className="muted">out of 100</div>
              <div className="bar"><i style={{ width: `${Math.min(result.score, 100)}%`, background: scoreColor }} /></div>
              <strong style={{ color: scoreColor }}>{verdict}</strong>
            </div>
            <h2>Matched keywords</h2>
            <div className="kw">{result.matched.length ? result.matched.map((k) => <span className="m" key={k}>{k}</span>) : <span className="muted">None found</span>}</div>
            <h2>Missing keywords</h2>
            <div className="kw">{result.missing.length ? result.missing.map((k) => <span className="x" key={k}>{k}</span>) : <span className="m">All matched!</span>}</div>
            <h2>Suggestions</h2>
            <ol className="sugs">{result.suggestions.map((s, i) => <li key={i}>{s}</li>)}</ol>
          </div>
        ) : (
          <div className="card placeholder"><strong>Your ATS score will appear here</strong><p className="muted">Upload your resume, paste the job description and tap Score my resume. You'll see matched keywords, what's missing and how to improve.</p></div>
        )}
        <h2 style={{ marginTop: 20 }}>Improve it</h2>
        <Rewrite key="existing" me={me} file={file} jd={jd} mode="existing" onUpgraded={setMe} />          </div>
        </div>
      )}
      </>)}
    </>
  );
}
