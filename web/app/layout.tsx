import type { Metadata, Viewport } from "next";
import "./globals.css";
import "./legal.css";

export const metadata: Metadata = {
  title: "ProfileIQ — AI Resume Intelligence",
  description: "Score your resume against any job description and see exactly which keywords you're missing.",
};
// Always serve fresh HTML so a phone never keeps a page that points at files from an older deploy.
export const dynamic = "force-dynamic";
export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0e0e0e" };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en"><body>
      {children}
      {/* Safety net: if the app's scripts fail to start (stale cache, flaky network), say so instead of leaving a dead page. */}
      <script dangerouslySetInnerHTML={{ __html: `setTimeout(function(){if(window.__piqReady)return;var d=document.createElement("div");d.style.cssText="position:fixed;left:12px;right:12px;bottom:12px;z-index:99;background:#2a1010;border:1px solid #5a2020;color:#fca5a5;border-radius:10px;padding:12px 14px;font:14px system-ui";d.innerHTML='This page did not load fully. <a href="" style="color:#f59e0b;font-weight:700" onclick="location.reload();return false">Reload</a>';document.body.appendChild(d)},8000)` }} />
    </body></html>
  );
}
