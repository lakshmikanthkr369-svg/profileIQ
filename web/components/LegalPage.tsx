import fs from "node:fs";
import path from "node:path";
import Link from "next/link";
import SiteFooter from "./SiteFooter";

// Static, trusted content kept in web/content/*.html (copied from the public site pages).
export default function LegalPage({ file, kind }: { file: string; kind: "about" | "doc" }) {
  const html = fs.readFileSync(path.join(process.cwd(), "content", `${file}.html`), "utf8");
  return (
    <main className="legalpage">
      <header className="legal-top">
        <Link href="/" className="brand" aria-label="ProfileIQ home"><span className="mark">IQ</span><span>Profile<b>IQ</b></span></Link>
        <Link href="/" className="backbtn">← Back to home</Link>
      </header>
      <article className={kind === "about" ? "about-page" : "doc-page"} dangerouslySetInnerHTML={{ __html: html }} />
      <div className="legal-top" style={{ borderBottom: "none", justifyContent: "center" }}>
        <Link href="/" className="backbtn">← Back to home</Link>
      </div>
      <SiteFooter />
    </main>
  );
}
