"use client";
import { useEffect, useRef, useState } from "react";
import { ApiError, getMe, scoreResume, type Me, type ScoreResult } from "@/lib/api";
import { supabase } from "@/lib/supabase";

const MAX_MB = 10;

export default function Dashboard() {
  const [me, setMe] = useState<Me | null>(null);
  const [meError, setMeError] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [jd, setJd] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<{ message: string; ref: string } | null>(null);
  const [result, setResult] = useState<ScoreResult | null>(null);
  const [tab, setTab] = useState<"score" | "rewrite">("score");
  const picker = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getMe().then(setMe).catch((e: ApiError) => setMeError(e.message));
  }, []);

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
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <div style={{ flex: "1 1 200px" }}>
          <strong style={{ wordBreak: "break-all" }}>{me?.email ?? "…"}</strong>{" "}
          {me?.is_pro && <span className="pill">PRO</span>}
          {me && !me.is_pro && <span className="muted" style={{ fontSize: 12 }}> · {me.scans_left} free scans left</span>}
        </div>
        <button className="ghost" style={{ flex: "0 0 auto", width: "auto" }} onClick={() => supabase.auth.signOut()}>Sign out</button>
      </div>
      {meError && <div className="err" role="alert">{meError}</div>}

      <div className="grid2" style={{ marginTop: 12 }}>
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

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "score"} className={tab === "score" ? "on" : ""} onClick={() => setTab("score")}>Score my resume</button>
        <button role="tab" aria-selected={tab === "rewrite"} className={tab === "rewrite" ? "on" : ""} onClick={() => setTab("rewrite")}>Rewrite with AI</button>
      </div>

      {tab === "rewrite" ? (
        <div className="card"><strong>Rewrite with AI is coming next.</strong>
          <p className="muted">This screen is being rebuilt. Your live app still has it today.</p></div>
      ) : (<>
        {error && <div className="err" role="alert">{error.message}<small>Reference: {error.ref}</small></div>}
        {outOfScans && <div className="err">You have used all 3 free scans this month. Upgrade to Pro for unlimited scans.</div>}
        <button onClick={analyze} disabled={busy || !!outOfScans}>{busy ? "Analyzing…" : "Analyze now"}</button>

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
      </>)}
    </>
  );
}
