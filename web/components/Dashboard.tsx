"use client";
import { useEffect, useRef, useState } from "react";
import { ApiError, confirmSubscription, getMe, scoreResume, type Me, type ScoreResult } from "@/lib/api";
import { supabase } from "@/lib/supabase";
import Rewrite from "./Rewrite";
import Upgrade from "./Upgrade";
import { Invoices, Subscription, Support } from "./Account";
import { PENDING_KEY, unlockPage } from "./Upgrade";

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

  // Coming back from a UPI app: make sure the page can scroll and nothing from checkout is left covering it.
  useEffect(() => {
    // On a fresh page load nothing from checkout can still be running, so clear everything. When the tab
    // merely comes back to the foreground, only fix scrolling (a payment may still be in progress).
    unlockPage(true);
    const back = () => unlockPage(false);
    const vis = () => { if (document.visibilityState === "visible") unlockPage(false); };
    window.addEventListener("pageshow", back);
    document.addEventListener("visibilitychange", vis);
    return () => { window.removeEventListener("pageshow", back); document.removeEventListener("visibilitychange", vis); };
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
        if (r?.status === "paid") { clear(); unlockPage(); setMe(await getMe()); setPayNote("Payment received — you're Pro now. Enjoy!"); return; }
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
      <div className="topbar">
        <div className="who">
          <strong>{me?.email ?? "…"}</strong>{" "}
          {me?.is_pro && <span className="pill">PRO</span>}
          {me && !me.is_pro && <span className="muted" style={{ fontSize: 12 }}> · {me.scans_left} free scans left</span>}
        </div>
        <div className="actions">
          {me?.has_billing && <button className="ghost" onClick={() => setPanel(panel === "billing" ? "" : "billing")}>{me.is_pro ? "Manage" : "Billing"}</button>}
          <button className="ghost" onClick={() => setPanel(panel === "support" ? "" : "support")}>Support</button>
          <button className="ghost" onClick={() => supabase.auth.signOut()}>Sign out</button>
        </div>
      </div>
      {payNote && <div className="ok" role="status">{payNote}</div>}
      {me?.is_pro && me.cancels_at_period_end && me.pro_expires_at && (
        <div className="notice warn" role="status"><strong>Your subscription is cancelled</strong>
          You still have Pro until {new Date(me.pro_expires_at).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}. It won&apos;t renew after that.</div>
      )}
      {me && !me.is_pro && me.plan_ended_on && (
        <div className="notice bad" role="status"><strong>Your Pro subscription has ended</strong>
          It ended on {new Date(me.plan_ended_on).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}. Upgrade to get Pro features back.</div>
      )}
      {panel === "billing" && (<><Subscription me={me} onChanged={setMe} /><Invoices /></>)}
      {panel === "support" && <Support me={me} onClose={() => setPanel("")} />}
      {meError && <div className="err" role="alert">{meError}</div>}
      {me && !me.is_pro && (
        <div className="card" style={{ margin: "12px 0" }}>
          <strong>Go Pro</strong>
          <p className="muted" style={{ margin: "6px 0 12px" }}>Unlimited scans, AI rewrite, fresher resume builder, 4 formats and PDF/Word downloads. Cancel any time.</p>
          <Upgrade me={me} onUpgraded={setMe} />
        </div>
      )}
      <div className="tabs" role="tablist" style={{ marginTop: 12 }}>
        <button role="tab" aria-selected={level === "existing"} className={level === "existing" ? "on" : ""} onClick={() => setLevel("existing")}>I&apos;m experienced</button>
        <button role="tab" aria-selected={level === "fresher"} className={level === "fresher" ? "on" : ""} onClick={() => setLevel("fresher")}>I&apos;m a fresher</button>
      </div>

      <div className="grid2" style={{ marginTop: 4 }}>
        {level === "existing" && (
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
        )}
        <div style={level === "fresher" ? { gridColumn: "1 / -1" } : undefined}>
          <h2>Job description</h2>
          <textarea value={jd} onChange={(e) => setJd(e.target.value)} placeholder="Paste the full job description here — the more detail, the better the match." />
        </div>
      </div>

      {level === "fresher" ? (
        <Rewrite key="fresher" me={me} file={null} jd={jd} mode="fresher" onUpgraded={setMe} />
      ) : (<>
        {error && <div className="err" role="alert">{error.message}<small>Reference: {error.ref}</small></div>}
        {outOfScans && <div className="err">You have used all 3 free scans this month. Upgrade to Pro for unlimited scans — use the Go Pro button above.</div>}
        <button onClick={analyze} aria-busy={busy} disabled={busy || !!outOfScans}>{busy ? "Analyzing…" : "Score my resume"}</button>

        {result && (
          <div className="card" style={{ marginTop: 16 }} aria-live="polite">
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
        )}

        <h2 style={{ marginTop: 24 }}>Improve it</h2>
        <Rewrite key="existing" me={me} file={file} jd={jd} mode="existing" onUpgraded={setMe} />
      </>)}
    </>
  );
}
