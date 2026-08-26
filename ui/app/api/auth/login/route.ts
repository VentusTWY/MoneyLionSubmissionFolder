import { authenticateDemoAdmin, createAdminSession, hasDemoAdminConfig, sessionCookie } from "../../../admin-auth";

export async function POST(request: Request) {
  if (!hasDemoAdminConfig()) return Response.json({ detail: "Demo login is not configured" }, { status: 503 });
  try {
    const body = await request.json() as { email?: string; password?: string };
    const user = await authenticateDemoAdmin(body.email ?? "", body.password ?? "");
    if (!user) return Response.json({ detail: "Invalid email or password" }, { status: 401 });
    return Response.json({ ok: true }, { headers: { "Set-Cookie": sessionCookie(await createAdminSession(user)) } });
  } catch {
    return Response.json({ detail: "Invalid request body" }, { status: 400 });
  }
}
