"use client";
import { useEffect, useState } from "react";
import { ApiError, emailInvoice, listInvoices, sendSupport, type Invoice, type Me } from "@/lib/api";

const rupees = (paise: number, cur: string) => `${cur === "INR" ? "₹" : cur + " "}${(paise / 100).toLocaleString("en-IN", { minimumFractionDigits: 2 })}`;
const day = (iso: string) => new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "Asia/Kolkata" });
const method = (m: string | null) => ({ upi: "UPI Autopay", card: "Card", netbanking: "Net banking", wallet: "Wallet", emandate: "e-Mandate" } as Record<string, string>)[m ?? ""] ?? "Online payment";

export function Invoices() {
  const [rows, setRows] = useState<Invoice[] | null>(null);
  const [err, setErr] = useState("");
  const [note, setNote] = useState<{ id: number; text: string; ok: boolean } | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  useEffect(() => { listInvoices().then((r) => setRows(r.invoices)).catch((e: ApiError) => setErr(e.message)); }, []);

  async function send(id: number) {
    setBusy(id); setNote(null);
    try { const r = await emailInvoice(id); setNote({ id, ok: true, text: `Sent to ${r.sent_to}. It can take a minute — check spam if you don't see it.` }); }
    catch (e) { setNote({ id, ok: false, text: (e as ApiError).message }); }
    finally { setBusy(null); }
  }

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <strong>Invoices</strong>
      {err && <div className="err" role="alert">{err}</div>}
      {rows === null && !err && <p className="muted">Loading…</p>}
      {rows?.length === 0 && <p className="muted">No invoices yet. They appear here after your first payment.</p>}
      {rows?.map((i) => (
        <div key={i.id} style={{ borderTop: "1px solid var(--line)", padding: "10px 0" }}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <div style={{ flex: "1 1 180px" }}>
              <strong>{i.invoice_number}</strong>
              <div className="muted" style={{ fontSize: 12 }}>{day(i.issued_at)} · {method(i.payment_method)} · {rupees(i.amount_paise, i.currency)}</div>
            </div>
            <button className="ghost" style={{ width: "auto", flex: "0 0 auto" }} disabled={busy === i.id} onClick={() => send(i.id)}>
              {busy === i.id ? "Sending…" : i.emailed_at ? "Email me again" : "Send to my email"}
            </button>
          </div>
          {note?.id === i.id && <div className={note.ok ? "ok" : "err"} role="status">{note.text}</div>}
        </div>
      ))}
    </div>
  );
}

export function Support({ me, onClose }: { me: Me | null; onClose: () => void }) {
  const [type, setType] = useState("Feedback");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState<{ message: string; ref: string } | null>(null);

  async function submit() {
    setErr(null);
    if (!message.trim()) return setErr({ message: "Please enter a message.", ref: "no-message" });
    setBusy(true);
    try { await sendSupport(type, message); setDone(true); }
    catch (e) { const x = e as ApiError; setErr({ message: x.message, ref: x.ref }); }
    finally { setBusy(false); }
  }

  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <strong>Support</strong>
      {done ? (<>
        <div className="ok" role="status">Submitted! We&apos;ll get back to you at {me?.email}.</div>
        <button className="ghost" onClick={onClose}>Close</button>
      </>) : (<>
        <label htmlFor="sup-type">Type</label>
        <select id="sup-type" value={type} onChange={(e) => setType(e.target.value)}>
          {["Feedback", "Bug Report", "Feature Request", "Other"].map((t) => <option key={t}>{t}</option>)}
        </select>
        <label htmlFor="sup-msg">Message</label>
        <textarea id="sup-msg" style={{ minHeight: 120 }} value={message} maxLength={4000} onChange={(e) => setMessage(e.target.value)} placeholder="Tell us what's on your mind…" />
        {err && <div className="err" role="alert">{err.message}<small>Reference: {err.ref}</small></div>}
        <div className="row" style={{ marginTop: 12 }}>
          <button onClick={submit} disabled={busy}>{busy ? "Sending…" : "Submit"}</button>
          <button className="ghost" onClick={onClose}>Cancel</button>
        </div>
      </>)}
    </div>
  );
}
