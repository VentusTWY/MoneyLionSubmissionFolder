import { proxy } from "../../route";

export async function POST(request: Request, { params }: { params: Promise<{ version: string }> }) {
  const { version } = await params;
  return proxy(`/v1/admin/models/${encodeURIComponent(version)}/promote`, request);
}
