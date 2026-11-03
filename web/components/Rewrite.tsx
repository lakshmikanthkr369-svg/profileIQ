"use client";
import { useEffect, useState } from "react";
import Upgrade from "./Upgrade";
import {
  ApiError, buildFresher, downloadResume, getTemplates, previewResume, rewriteResume,
  type FresherProfile, type Me, type ResumeData,
} from "@/lib/api";

const EMPTY: FresherProfile = {
  full_name: "", email: "", phone: "", degree: "", institute: "", university: "", year_of_passing: "",
  key_skills: "", projects: [{ name: "", description: "" }], certifications: [],
};

interface Props { me: Me | null; file: File | null; jd: string; onUpgraded: (m: Me) => void }
type Err = { message: string; ref: string } | null;

export default function Rewrite({ me, file, jd, onUpgraded }: Props) {
  const [mode, setMode] = useState<"existing" | "fresher">("existing");
  const [templates, setTemplates] = useState<string[]>([]);
  const [template, setTemplate] = useState("Bold");
  const [data, setData] = useState<ResumeData | null>(null);
  const [after, setAfter] = useState<number | null>(null);
  const [html, setHtml] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState<Err>(null);
  const [fresher, setFresher] = useState<FresherProfile>({ ...EMPTY, email: me?.email ?? "" });

  useEffect(() => { getTemplates().then((t) => setTemplates(t.templates)).catch(() => setTemplates(["Bold"])); }, []);
  useEffect(() => { if (me?.email) setFresher((f) => (f.email ? f : { ...f, email: me.email })); }, [me?.email]);

  // Live preview: refresh whenever the resume or template changes.
  useEffect(() => {
    if (!data) return;
    let stale = false;
    previewResume(data, template).then((r) => { if (!stale) setHtml(r.html); })
      .catch((e: ApiError) => { if (!stale) setError({ message: e.message, ref: e.ref }); });
    return () => { stale = true; };
  }, [data, template]);

  const fail = (e: unknown) => { const x = e as ApiError; setError({ message: x.message, ref: x.ref }); };

  async function runRewrite() {
    setError(null);
    if (!file) return setError({ message: "Upload your resume above first.", ref: "no-file" });
    if (!jd.trim()) return setError({ message: "Paste a job description above first.", ref: "no-jd" });
    setBusy("Rewriting your resume — this takes about 30 seconds…");
    try { const r = await rewriteResume(file, jd); setData(r.data); setAfter(r.after_score); }
    catch (e) { fail(e); } finally { setBusy(""); }
  }

  async function runFresher() {
    setError(null);
    if (!jd.trim()) return setError({ message: "Paste a job description above first.", ref: "no-jd" });
    setBusy("Building your resume — this takes about 30 seconds…");
    try {
      const p = { ...fresher, projects: fresher.projects.filter((x) => x.name.trim()), certifications: fresher.certifications.filter((c) => c.name.trim()) };
      const r = await buildFresher(p, jd); setData(r.data); setAfter(null);
    } catch (e) { fail(e); } finally { setBusy(""); }
  }

  async function download(format: "pdf" | "docx") {
    if (!data) return;
    setError(null); setBusy("Preparing your download…");
    try { await downloadResume(data, template, format); } catch (e) { fail(e); } finally { setBusy(""); }
  }

  const set = (k: keyof FresherProfile) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setFresher((f) => ({ ...f, [k]: e.target.value }));

  const locked = !!me && !me.is_pro;

  return (
    <>
      {locked && (
        <div className="card" style={{ marginBottom: 12 }}>
          <strong>Rewrite with AI is a Pro feature.</strong>
          <p className="muted" style={{ margin: "6px 0 12px" }}>Upgrade to Pro to get an ATS-optimised rewrite, four resume formats and PDF/Word downloads — for experienced professionals and freshers alike.</p>
          <Upgrade me={me} onUpgraded={onUpgraded} />
        </div>
      )}
      <div className="tabs" role="tablist" style={{ marginTop: 0 }}>
        <button className={mode === "existing" ? "on" : ""} onClick={() => setMode("existing")}>I'm experienced — I have a resume</button>
        <button className={mode === "fresher" ? "on" : ""} onClick={() => setMode("fresher")}>I&apos;m a fresher</button>
      </div>

      {mode === "existing" ? (
        <button onClick={runRewrite} disabled={!!busy || locked}>{busy && !data ? "Working…" : locked ? "Rewrite my resume (Pro)" : "Rewrite my resume"}</button>
      ) : (
        <div className="card">
          <p className="muted" style={{ marginTop: 0 }}>No resume yet? Tell us about yourself and we&apos;ll build one for this job.</p>
          <div className="grid2">
            <label>Full name *<input type="text" value={fresher.full_name} onChange={set("full_name")} /></label>
            <label>Email *<input type="email" value={fresher.email} onChange={set("email")} /></label>
            <label>Phone<input type="tel" value={fresher.phone} onChange={set("phone")} /></label>
            <label>Degree *<input type="text" value={fresher.degree} onChange={set("degree")} placeholder="B.Tech Computer Science" /></label>
            <label>Institute *<input type="text" value={fresher.institute} onChange={set("institute")} /></label>
            <label>University<input type="text" value={fresher.university} onChange={set("university")} /></label>
            <label>Year of passing<input type="text" value={fresher.year_of_passing} onChange={set("year_of_passing")} /></label>
          </div>
          <label>Key skills * (comma separated)<textarea value={fresher.key_skills} onChange={set("key_skills")} /></label>
          <h2>Projects</h2>
          {fresher.projects.map((p, i) => (
            <div key={i} style={{ marginBottom: 10 }}>
              <input type="text" placeholder="Project name" value={p.name}
                onChange={(e) => setFresher((f) => ({ ...f, projects: f.projects.map((x, j) => j === i ? { ...x, name: e.target.value } : x) }))} />
              <textarea placeholder="What did you build and which tools did you use?" value={p.description}
                onChange={(e) => setFresher((f) => ({ ...f, projects: f.projects.map((x, j) => j === i ? { ...x, description: e.target.value } : x) }))} />
            </div>
          ))}
          <button className="ghost" onClick={() => setFresher((f) => ({ ...f, projects: [...f.projects, { name: "", description: "" }] }))}>+ Add project</button>
          <h2>Certifications</h2>
          {fresher.certifications.map((c, i) => (
            <input key={i} type="text" placeholder="Certification name" value={c.name} style={{ marginBottom: 8 }}
              onChange={(e) => setFresher((f) => ({ ...f, certifications: f.certifications.map((x, j) => j === i ? { name: e.target.value } : x) }))} />
          ))}
          <button className="ghost" onClick={() => setFresher((f) => ({ ...f, certifications: [...f.certifications, { name: "" }] }))}>+ Add certification</button>
          <div style={{ height: 12 }} />
          <button onClick={runFresher} disabled={!!busy || locked}>{locked ? "Build my resume (Pro)" : "Build my resume"}</button>
        </div>
      )}

      {busy && <p className="muted" aria-live="polite">{busy}</p>}
      {error && <div className="err" role="alert">{error.message}<small>Reference: {error.ref}</small></div>}

      {data && (
        <div className="card" style={{ marginTop: 16 }}>
          {after !== null && <p><strong>New ATS score: {after}/100</strong></p>}
          <h2>Choose a format</h2>
          <div className="tabs" style={{ flexWrap: "wrap", marginTop: 0 }}>
            {templates.map((t) => (
              <button key={t} className={t === template ? "on" : ""} onClick={() => setTemplate(t)}>{t}</button>
            ))}
          </div>
          {html && <iframe title="Resume preview" sandbox="" srcDoc={html}
            style={{ width: "100%", height: 560, border: "1px solid var(--line)", borderRadius: 10, background: "#fff" }} />}
          <div className="row" style={{ marginTop: 12 }}>
            <button onClick={() => download("pdf")} disabled={!!busy}>Download PDF</button>
            <button onClick={() => download("docx")} disabled={!!busy}>Download Word</button>
          </div>
        </div>
      )}
    </>
  );
}
