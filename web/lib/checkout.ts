// Shared state + helpers for the Razorpay payment screen (see components/Upgrade.tsx).
export const PENDING_KEY = "piq_pending_sub";

let open = false;
const listeners = new Set<(o: boolean) => void>();
export const isCheckoutOpen = () => open;
export function setCheckoutOpen(v: boolean) { open = v; listeners.forEach((f) => f(v)); }
export function onCheckoutChange(f: (o: boolean) => void) { listeners.add(f); return () => { listeners.delete(f); }; }

/** True when something is stopping the page from scrolling (inline OR stylesheet lock). */
export function pageIsLocked(): boolean {
  try {
    const b = getComputedStyle(document.body), h = getComputedStyle(document.documentElement);
    return b.overflowY === "hidden" || h.overflowY === "hidden" || b.position === "fixed" || b.touchAction === "none";
  } catch { return false; }
}

/** Put the page back to normal. Razorpay locks scrolling while checkout is open and, on phones (UPI app
 *  hand-off), can forget to unlock it or leave its full-screen layer behind. */
export function unlockPage(removeLayer = true) {
  try {
    // First drop whatever the payment screen set directly on the page, so a normal page is left untouched.
    const html = document.documentElement, body = document.body;
    for (const el of [html, body]) for (const p of ["overflow", "overflow-x", "overflow-y", "position", "height", "top", "touch-action"]) el.style.removeProperty(p);
    // Only if something in a stylesheet still locks it, force it open. The page (html) is the one scroller;
    // body must NOT scroll on its own, or phones get a second nested scroller and the page sticks.
    if (pageIsLocked()) {
      html.style.setProperty("overflow-y", "auto", "important");
      body.style.setProperty("overflow", "visible", "important");
      body.style.setProperty("position", "static", "important");
      body.style.setProperty("touch-action", "auto", "important");
    }
    document.body.classList.remove("razorpay-checkout-open");
    if (removeLayer) {
      document.querySelectorAll(".razorpay-container, iframe.razorpay-checkout-frame").forEach((n) => n.remove());
      setCheckoutOpen(false);
    }
  } catch { /* nothing to undo */ }
}
