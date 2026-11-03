/** Accepts 9876543210, +91 98765 43210, 91-9876543210, 09876543210. Returns +91XXXXXXXXXX or null. */
export function normalizeIndianMobile(raw: string): string | null {
  let d = (raw || "").replace(/\D/g, "");
  if (d.length === 12 && d.startsWith("91")) d = d.slice(2);
  else if (d.length === 11 && d.startsWith("0")) d = d.slice(1);
  return d.length === 10 && "6789".includes(d[0]) ? `+91${d}` : null;
}
export const isValidEmail = (e: string) => /^[^@\s]+@[^@\s]+\.[^@\s]{2,}$/.test((e || "").trim());
