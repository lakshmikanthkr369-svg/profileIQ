"use client";
import { useCallback, useEffect, useState } from "react";
import { ApiError, adminMe, adminStats, adminUpdate, adminUser, adminUsers, type AdminEditResult, type AdminInvoice, type AdminUser } from "@/lib/api";
import { supabase } from "@/lib/supabase";

type Gate = "checking" | "login" | "denied" | "in";
const FILTERS = [["all", "All"], ["active", "Active Pro"], ["cancelled", "Cancelled"], ["free", "Free"]] as const;
const LABEL: Record<AdminUser["status"], string> = { free: "Free", active: "Active", cancelled: "Cancelled", expired: "Expired" };
const d = (iso?: string | null) => (iso ? new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—");

export default function AdminApp() {
  const [gate, setGate] = useState<Gate>("checking");
  const [who, setWho] = useState("");

  const check = useCallback(async () => {
    const { data } = await supabase.auth.getSession();
    if (!data.session) { setGate("login"); return; }
    try { const m = await adminMe(); setWho(m.email); setGate("in"); }
    catch (e) { setGate((e as ApiError).status === 403 ? "denied" : "login"); }
  }, []);
  useEffect(() => { check(); }, [check]);

  async function signOut() { await supabase.auth.signOut(); setWho(""); setGate("login"); }

  if (gate === "checking") return <main className="adminpage"><p className="muted" style={{ padding: 40 }}>Checking access…</p></main>;
  if (gate === "login") return <Login onDone={check} />;
  if (gate === "denied") return (
    <main className="adminpage"><div className="card adm-narrow">
      <h1 className="acct-title">No access</h1>
      <p className="muted">This account isn&apos;t allowed to open the admin area.</p>
      <button onClick={signOut} style={{ marginTop: 14 }}>Sign out</button>
    </div></main>
  );
  return <Console who={who} onSignOut={signOut} />;
}

function Login({ onDone }: { onDone: () => void }) {
  const [err, setErr] = useState(""); const [busy, setBusy] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault(); if (busy) return;
    const f = new FormData(e.currentTarget);
    const email = String(f.get("email") ?? "").trim(); const password = String(f.get("password") ?? "");
    if (!email || !password) { setErr("Enter your email and password."); return; }
    setBusy(true); setErr("");
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    if (error) { setErr("That email or password isn't right."); setBusy(false); return; }
    try { await adminMe(); onDone(); }
    catch (x) {
      await supabase.auth.signOut();
      setErr((x as ApiError).status === 403 ? "This account doesn't have admin access." : "Couldn't verify access. Please try again.");
    }
    setBusy(false);
  }
  return (
    <main className="adminpage">
      <form className="card adm-narrow" onSubmit={submit} method="post" action="#">
        <div className="brand" style={{ marginBottom: 14 }}><span className="mark">IQ</span><span>Profile<b>IQ</b> <span className="muted">Admin</span></span></div>
        <label htmlFor="ae">Email</label>
        <input id="ae" name="email" type="email" autoComplete="username" required />
        <label htmlFor="ap">Password</label>
        <input id="ap" name="password" type="password" autoComplete="current-password" required />
        {err && <div className="err" role="alert">{err}</div>}
        <button type="submit" aria-busy={busy} disabled={busy} style={{ marginTop: 16 }}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
    </main>
  );
}

function Console({ who, onSignOut }: { who: string; onSignOut: () => void }) {
  const [stats, setStats] = useState<{ total: number; active: number; cancelled: number } | null>(null);
  const [q, setQ] = useState(""); const [filter, setFilter] = useState("all");
  const [users, setUsers] = useState<AdminUser[]>([]); const [more, setMore] = useState(false);
  const [loading, setLoading] = useState(true); const [error, setError] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);

  const load = useCallback(async (reset = true, offset = 0) => {
    setLoading(true); setError("");
    try {
      const r = await adminUsers(q, filter, offset);
      setUsers((u) => (reset ? r.users : [...u, ...r.users])); setMore(r.has_more);
    } catch (e) { setError((e as ApiError).message); }
    setLoading(false);
  }, [q, filter]);

  useEffect(() => { const t = setTimeout(() => load(true), 300); return () => clearTimeout(t); }, [load]);
  useEffect(() => { adminStats().then(setStats).catch(() => {}); }, []);

  if (openId) return <Detail id={openId} who={who} onBack={() => { setOpenId(null); load(true); adminStats().then(setStats).catch(() => {}); }} onSignOut={onSignOut} />;

  return (
    <main className="adminpage">
      <Bar who={who} onSignOut={onSignOut} />
      <div className="adm-stats">
        <div className="card"><span>Total users</span><b>{stats?.total ?? "—"}</b></div>
        <div className="card"><span>Active Pro</span><b>{stats?.active ?? "—"}</b></div>
        <div className="card"><span>Cancelled (still Pro)</span><b>{stats?.cancelled ?? "—"}</b></div>
      </div>
      <div className="adm-tools">
        <input type="text" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, email or mobile" aria-label="Search users" />
        <div className="tabs" role="tablist">
          {FILTERS.map(([k, l]) => <button key={k} role="tab" aria-selected={filter === k} className={filter === k ? "on" : ""} onClick={() => setFilter(k)}>{l}</button>)}
        </div>
      </div>
      {error && <div className="err" role="alert">{error}</div>}
      <div className="adm-table card" aria-busy={loading}>
        <div className="adm-row adm-head"><span>User</span><span>Mobile</span><span>Status</span><span>Pro until</span><span>Joined</span></div>
        {users.map((u) => (
          <button key={u.id} className="adm-row" onClick={() => setOpenId(u.id)}>
            <span><b>{u.full_name || "—"}</b><small>{u.email || "no email"}</small></span>
            <span data-l="Mobile">{u.phone || "—"}</span>
            <span data-l="Status"><i className={`st ${u.status}`}>{LABEL[u.status]}</i></span>
            <span data-l="Pro until">{u.status === "free" ? "—" : d(u.pro_expires_at)}</span>
            <span data-l="Joined">{d(u.created_at)}</span>
          </button>
        ))}
        {!loading && users.length === 0 && <p className="muted" style={{ padding: 18 }}>No users match.</p>}
        {loading && <p className="muted" style={{ padding: 18 }}>Loading…</p>}
      </div>
      {more && !loading && <button className="ghost" style={{ marginTop: 14 }} onClick={() => load(false, users.length)}>Load more</button>}
    </main>
  );
}

function Bar({ who, onSignOut, back }: { who: string; onSignOut: () => void; back?: () => void }) {
  return (
    <header className="adm-bar">
      <div className="row" style={{ flex: "0 0 auto", gap: 12 }}>
        {back && <button className="backbtn" style={{ margin: 0 }} onClick={back}>← All users</button>}
        <div className="brand"><span className="mark">IQ</span><span>Admin</span></div>
      </div>
      <div className="row" style={{ flex: "0 0 auto", gap: 10 }}>
        <span className="muted adm-who">{who}</span>
        <button className="ghost" style={{ width: "auto", minHeight: 40, padding: "8px 14px" }} onClick={onSignOut}>Sign out</button>
      </div>
    </header>
  );
}

function Detail({ id, who, onBack, onSignOut }: { id: string; who: string; onBack: () => void; onSignOut: () => void }) {
  const [u, setU] = useState<AdminUser | null>(null); const [inv, setInv] = useState<AdminInvoice[]>([]);
  const [name, setName] = useState(""); const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false); const [err, setErr] = useState(""); const [res, setRes] = useState<AdminEditResult | null>(null);

  const fill = (x: AdminUser) => { setU(x); setName(x.full_name ?? ""); setPhone(x.phone ?? ""); };
  useEffect(() => { adminUser(id).then((r) => { fill(r.user); setInv(r.invoices); }).catch((e) => setErr((e as ApiError).message)); }, [id]);

  const dirty = !!u && (name.trim() !== (u.full_name ?? "") || phone.trim() !== (u.phone ?? ""));

  async function save(e: React.FormEvent) {
    e.preventDefault(); if (!u || busy || !dirty) return;
    setBusy(true); setErr(""); setRes(null);
    const body: { full_name?: string; phone?: string } = {};
    if (name.trim() !== (u.full_name ?? "")) body.full_name = name;
    if (phone.trim() !== (u.phone ?? "") && phone.trim()) body.phone = phone;
    try { const r = await adminUpdate(id, body); setRes(r); fill({ ...u, ...r.user }); }
    catch (x) { setErr((x as ApiError).message); }
    setBusy(false);
  }

  return (
    <main className="adminpage">
      <Bar who={who} onSignOut={onSignOut} back={onBack} />
      {err && !u && <div className="err" role="alert">{err}</div>}
      {u && (
        <div className="adm-detail">
          <section className="card">
            <h2 className="adm-h">Contact details</h2>
            <p className="muted" style={{ fontSize: 13, margin: "0 0 4px" }}>The name and mobile are used in invoices, subscription and cancellation emails, and on the Razorpay customer record.</p>
            <form onSubmit={save}>
              <label htmlFor="n">Name</label><input id="n" type="text" value={name} onChange={(e) => setName(e.target.value)} autoComplete="off" />
              <label htmlFor="m">Email (cannot be changed)</label><input id="m" type="email" value={u.email ?? ""} readOnly disabled />
              <label htmlFor="p">Mobile</label><input id="p" type="tel" value={phone} onChange={(e) => setPhone(e.target.value)} autoComplete="off" placeholder="10-digit mobile" />
              {err && <div className="err" role="alert">{err}</div>}
              {res && (
                <div className="ok" role="status">
                  Saved.
                  {res.razorpay_updated === true && " Razorpay customer updated."}
                  {res.razorpay_updated === false && " ⚠ Razorpay couldn't be updated — change it in the Razorpay dashboard if needed."}
                  {res.razorpay_updated === null && " (No Razorpay customer on file.)"}
                </div>
              )}
              <button type="submit" disabled={!dirty || busy} aria-busy={busy} style={{ marginTop: 16 }}>{busy ? "Saving…" : "Save changes"}</button>
              <p className="muted" style={{ fontSize: 12, marginTop: 10 }}>Email is read-only: it is the address the user logs in with and receives notifications on.</p>
            </form>
          </section>
          <section className="card">
            <h2 className="adm-h">Subscription</h2>
            <dl className="adm-dl">
              <dt>Status</dt><dd><i className={`st ${u.status}`}>{LABEL[u.status]}</i></dd>
              <dt>Plan</dt><dd>{u.plan ?? "free"}</dd>
              <dt>Pro until</dt><dd>{u.status === "free" ? "—" : d(u.pro_expires_at)}</dd>
              <dt>Renewal</dt><dd>{u.status === "cancelled" ? "Cancelled — won't renew" : u.status === "active" ? "Auto-renews" : "—"}</dd>
              <dt>Joined</dt><dd>{d(u.created_at)}</dd>
              <dt>Free scans used</dt><dd>{u.scans_used ?? 0}</dd>
              <dt>Subscription ID</dt><dd className="mono">{u.razorpay_subscription_id ?? "—"}</dd>
              <dt>Customer ID</dt><dd className="mono">{u.razorpay_customer_id ?? "—"}</dd>
              <dt>User ID</dt><dd className="mono">{u.id}</dd>
            </dl>
            <h2 className="adm-h" style={{ marginTop: 22 }}>Invoices</h2>
            {inv.length === 0 ? <p className="muted">No invoices.</p> : (
              <ul className="adm-inv">
                {inv.map((i) => (
                  <li key={i.id}><span><b>{i.invoice_number ?? `#${i.id}`}</b><small>{d(i.issued_at)} · {i.payment_method ?? "—"}</small></span>
                    <span>{i.currency === "INR" ? "₹" : i.currency + " "}{(i.amount_paise / 100).toFixed(2)}</span></li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
