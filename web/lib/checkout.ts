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
    for (const el of [document.documentElement, document.body]) {
      el.style.setProperty("overflow", "visible", "important");
      el.style.setProperty("overflow-y", "auto", "important");
      el.style.setProperty("position", "static", "important");
      el.style.setProperty("height", "auto", "important");
      el.style.setProperty("touch-action", "auto", "important");
    }
    document.body.classList.remove("razorpay-checkout-open");
    if (removeLayer) {
      document.querySelectorAll(".razorpay-container, iframe.razorpay-checkout-frame").forEach((n) => n.remove());
      setCheckoutOpen(false);
    }
  } catch { /* nothing to undo */ }
}
