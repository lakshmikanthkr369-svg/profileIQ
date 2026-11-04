"use client";
import { useEffect, useRef, useState } from "react";
import type { Me } from "@/lib/api";

type Props = { me: Me | null; onManage: () => void; onSupport: () => void; onSignOut: () => void };

export default function ProfileMenu({ me, onManage, onSupport, onSignOut }: Props) {
  const [open, setOpen] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const name = me?.full_name?.trim() || me?.email?.split("@")[0] || "Account";
  const initial = name.charAt(0).toUpperCase();

  useEffect(() => {
    if (!open) return;
    const away = (e: Event) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") setOpen(false); };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", esc); };
  }, [open]);

  const pick = (fn: () => void) => () => { setOpen(false); fn(); };

  return (
    <div className="pmenu" ref={box}>
      <button className="pmenu-btn" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span className="avatar" aria-hidden="true">{initial}</span>
        <span className="pname">{name}</span>
        {me?.is_pro && <span className="pill">PRO</span>}
        <span className="caret" aria-hidden="true">▾</span>
      </button>
      {open && (
        <div className="pmenu-list" role="menu">
          <div className="pmenu-head">
            <strong>{name}</strong>
            <span>{me?.email}</span>
            {me && !me.is_pro && <span>{me.scans_left} free scans left</span>}
          </div>
          {me?.has_billing && <button role="menuitem" onClick={pick(onManage)}>{me.is_pro ? "Manage plan" : "Billing & invoices"}</button>}
          <button role="menuitem" onClick={pick(onSupport)}>Support</button>
          <button role="menuitem" className="danger" onClick={pick(onSignOut)}>Sign out</button>
        </div>
      )}
    </div>
  );
}
