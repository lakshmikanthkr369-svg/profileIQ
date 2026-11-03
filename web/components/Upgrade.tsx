"use client";
import { useState } from "react";
import { ApiError, confirmSubscription, getMe, startSubscription, type Me, type Subscribe } from "@/lib/api";
import { normalizeIndianMobile } from "@/lib/validate";

declare global {
  interface Window {
    Razorpay?: new (o: Record<string, unknown>) => { open(): void; on(e: string, cb: (r: { error: { description: string } }) => void): void };
  }
}

function loadCheckout(): Promise<void> {
  if (window.Razorpay) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = "https://checkout.razorpay.com/v1/checkout.js";
    s.onload = () => resolve();
    s.onerror = () => reject(new Error("load"));
    document.head.appendChild(s);
  });
}

export const PENDING_KEY = "piq_pending_sub";
/** Razorpay locks page scrolling while checkout is open and, on some phones (UPI app hand-off), forgets to
 *  unlock it or leaves its full-screen layer behind. Put the page back to normal. */
export function unlockPage(removeLayer = true) {
  try {
    for (const el of [document.documentElement, document.body]) {
      el.style.overflow = ""; el.style.position = ""; el.style.height = ""; el.style.top = ""; el.style.touchAction = "";
    }
    document.body.classList.remove("razorpay-checkout-open");
    if (removeLayer) document.querySelectorAll(".razorpay-container, iframe.razorpay-checkout-frame").forEach((n) => n.remove());
  } catch { /* nothing to undo */ }
}

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

interface Props { me: Me | null; onUpgraded: (m: Me) => void; label?: string; compact?: boolean }

export default function Upgrade({ me, onUpgraded, label = "Upgrade to Pro — ₹199/month", compact }: Props) {
  const [mobile, setMobile] = useState("");
  const [askMobile, setAskMobile] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState<{ message: string; ref: string } | null>(null);

  async function activate(subId: string) {
    setMsg("Payment received — activating your Pro plan…");
    for (let i = 0; i < 8; i++) {                // payment confirmation can take a few seconds
      const r = await confirmSubscription(subId).catch(() => null);
      if (r?.status === "paid") { try { localStorage.removeItem(PENDING_KEY); } catch { /* ignore */ } onUpgraded(await getMe()); setMsg("You're Pro now. Enjoy!"); return; }
      await wait(2500);
    }
    setMsg("");
    setError({ message: "Your payment went through but activation is taking longer than usual. Refresh the page in a minute — if you're still not Pro, contact support.", ref: subId });
  }

  async function begin() {
    setError(null); setMsg("");
    let phone: string | undefined;
    if (!me?.has_mobile) {
      phone = normalizeIndianMobile(mobile) ?? undefined;
      if (!phone) { setAskMobile(true); if (mobile) setError({ message: "Please enter a valid 10-digit Indian mobile number.", ref: "bad-mobile" }); return; }
    }
    setBusy(true);
    try {
      const sub: Subscribe = await startSubscription(phone);
      try { localStorage.setItem(PENDING_KEY, JSON.stringify({ id: sub.subscription_id, ts: Date.now() })); } catch { /* storage blocked */ }
      await loadCheckout();
      if (!window.Razorpay) throw new ApiError("Secure checkout couldn't load. Check your connection and try again.", "checkout-load", 0);
      const rzp = new window.Razorpay({
        key: sub.key_id, subscription_id: sub.subscription_id, name: "ProfileIQ",
        description: "ProfileIQ Pro — monthly subscription",
        prefill: { email: sub.email, contact: sub.contact }, theme: { color: "#F59E0B" },
        handler: () => { unlockPage(); setBusy(true); activate(sub.subscription_id).finally(() => { setBusy(false); unlockPage(); }); },
        modal: { ondismiss: () => { unlockPage(); setBusy(false); setMsg("Checkout closed. Tap Upgrade to try again."); } },
      });
      rzp.on("payment.failed", (r) => { unlockPage(); setBusy(false); setError({ message: `Payment failed: ${r.error.description}`, ref: "payment-failed" }); });
      rzp.open();
      setBusy(false);
    } catch (e) {
      const x = e as ApiError; setBusy(false);
      setError({ message: x.message ?? "Something went wrong.", ref: x.ref ?? "unknown" });
    }
  }

  return (
    <div>
      {askMobile && !me?.has_mobile && (
        <div style={{ marginBottom: 10 }}>
          <label htmlFor="up-mobile">Mobile number — for your invoice and payment updates</label>
          <input id="up-mobile" type="tel" inputMode="numeric" autoComplete="tel" value={mobile}
            onChange={(e) => setMobile(e.target.value)} placeholder="10-digit mobile, e.g. 98765 43210" />
        </div>
      )}
      <button onClick={begin} aria-busy={busy} disabled={busy} style={compact ? { width: "auto" } : undefined}>
        {busy ? "Please wait…" : label}
      </button>
      {msg && <p className="muted" aria-live="polite">{msg}</p>}
      {error && <div className="err" role="alert">{error.message}<small>Reference: {error.ref}</small></div>}
    </div>
  );
}
