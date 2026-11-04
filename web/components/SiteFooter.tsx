import Link from "next/link";

export default function SiteFooter() {
  return (
    <footer className="foot">
      <nav aria-label="Footer">
        <Link href="/about">About Us</Link>
        <Link href="/privacy">Privacy Policy</Link>
        <Link href="/terms">Terms</Link>
        <Link href="/refund">Refund Policy</Link>
        <a href="mailto:support@profileiq.co.in">Contact</a>
      </nav>
      <p>© {new Date().getFullYear()} ProfileIQ. All rights reserved.</p>
    </footer>
  );
}
