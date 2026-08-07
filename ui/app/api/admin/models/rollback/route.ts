import { proxy } from "../route";

export async function POST(request: Request) {
  return proxy("/v1/admin/models/rollback", request);
}
