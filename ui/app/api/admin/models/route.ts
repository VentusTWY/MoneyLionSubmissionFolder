import { getAdminUser } from "../../../admin-auth";

const apiBase = process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function GET() {
  return proxy("/v1/admin/models");
}

async function proxy(path: string, request?: Request) {
  const admin = await getAdminUser();
  if (!admin) return Response.json({ detail: "Forbidden" }, { status: 403 });
  const key = process.env.ADMIN_API_KEY;
  if (!key) return Response.json({ detail: "Admin service is not configured" }, { status: 503 });
  let body: string | undefined;
  if (request) {
    try {
      const payload = await request.json() as Record<string, unknown>;
      body = JSON.stringify({ ...payload, actor: admin.displayName });
    } catch {
      return Response.json({ detail: "Invalid request body" }, { status: 400 });
    }
  }
  const response = await fetch(`${apiBase}${path}`, {
    method: request?.method ?? "GET",
    headers: { "Content-Type": "application/json", "X-Admin-API-Key": key },
    body,
  });
  return new Response(response.body, { status: response.status, headers: { "Content-Type": response.headers.get("Content-Type") ?? "application/json" } });
}

export { proxy };
