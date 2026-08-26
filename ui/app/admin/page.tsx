import Link from "next/link";
import { redirect } from "next/navigation";
import AdminPanel from "./AdminPanel";
import { getAdminUser } from "../admin-auth";

export const dynamic = "force-dynamic";

export default async function AdminPage() {
  const admin = await getAdminUser();
  if (!admin) redirect("/login?return_to=%2Fadmin");

  return <main><header className="topbar"><Link className="brand" href="/" aria-label="LoanRiskCalculator home"><span className="brand-mark">LRC</span><span><strong>LoanRiskCalculator</strong><small>Decision intelligence</small></span></Link><div className="admin-navigation"><Link className="staff-sign-in" href="/">Scoring workspace</Link><a className="staff-sign-in" href="/api/auth/logout">Sign out</a></div></header><AdminPanel actor={admin.displayName} /></main>;
}
