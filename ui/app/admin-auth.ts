import { cookies } from "next/headers";

type AdminUser = { email: string; displayName: string };

const SESSION_COOKIE = "loanrisk_admin_session";
const encoder = new TextEncoder();

function config() {
  return {
    email: (process.env.ADMIN_DEMO_EMAIL ?? "").trim().toLowerCase(),
    password: process.env.ADMIN_DEMO_PASSWORD ?? "",
    secret: process.env.ADMIN_SESSION_SECRET ?? "",
  };
}

function base64UrlEncode(value: string | Uint8Array): string {
  const bytes = typeof value === "string" ? encoder.encode(value) : value;
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
}

function base64UrlDecode(value: string): string | null {
  try {
    const padded = value.replaceAll("-", "+").replaceAll("_", "/") + "=".repeat((4 - value.length % 4) % 4);
    return new TextDecoder().decode(Uint8Array.from(atob(padded), (character) => character.charCodeAt(0)));
  } catch {
    return null;
  }
}

async function signature(value: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return base64UrlEncode(new Uint8Array(await crypto.subtle.sign("HMAC", key, encoder.encode(value))));
}

function safelyEqual(left: string, right: string): boolean {
  const leftBytes = encoder.encode(left);
  const rightBytes = encoder.encode(right);
  if (leftBytes.length !== rightBytes.length) return false;
  let difference = 0;
  for (let index = 0; index < leftBytes.length; index += 1) difference |= leftBytes[index] ^ rightBytes[index];
  return difference === 0;
}

export function hasDemoAdminConfig(): boolean {
  const { email, password, secret } = config();
  return Boolean(email && password && secret);
}

export async function authenticateDemoAdmin(email: string, password: string): Promise<AdminUser | null> {
  const configured = config();
  if (!configured.email || !configured.password || !configured.secret) return null;
  const normalizedEmail = email.trim().toLowerCase();
  if (!safelyEqual(normalizedEmail, configured.email) || !safelyEqual(password, configured.password)) return null;
  return { email: configured.email, displayName: configured.email };
}

export async function createAdminSession(user: AdminUser): Promise<string> {
  const { secret } = config();
  const payload = base64UrlEncode(JSON.stringify({ email: user.email, expires: Math.floor(Date.now() / 1000) + 60 * 60 * 8 }));
  return `${payload}.${await signature(payload, secret)}`;
}

export async function getAdminUser(): Promise<AdminUser | null> {
  const { email: configuredEmail, secret } = config();
  const token = (await cookies()).get(SESSION_COOKIE)?.value;
  if (!configuredEmail || !secret || !token) return null;
  const [payload, receivedSignature] = token.split(".");
  if (!payload || !receivedSignature || !safelyEqual(receivedSignature, await signature(payload, secret))) return null;
  const decoded = base64UrlDecode(payload);
  if (!decoded) return null;
  try {
    const session = JSON.parse(decoded) as { email?: string; expires?: number };
    if (session.email !== configuredEmail || !session.expires || session.expires < Date.now() / 1000) return null;
    return { email: configuredEmail, displayName: configuredEmail };
  } catch {
    return null;
  }
}

export function sessionCookie(value: string): string {
  return `${SESSION_COOKIE}=${value}; Path=/; HttpOnly; SameSite=Lax; Max-Age=28800${process.env.NODE_ENV === "production" ? "; Secure" : ""}`;
}

export function expiredSessionCookie(): string {
  return `${SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`;
}
