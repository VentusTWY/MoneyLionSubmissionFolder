import { expiredSessionCookie } from "../../../admin-auth";

export async function GET(request: Request) {
  return new Response(null, { status: 303, headers: { Location: new URL("/", request.url).toString(), "Set-Cookie": expiredSessionCookie() } });
}
