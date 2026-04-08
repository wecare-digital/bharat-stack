/**
 * Server-side admin password verification endpoint.
 * 
 * NOTE: This route requires removing `output: 'export'` from next.config.js
 * or switching to a hybrid rendering mode. With static export, API routes
 * are not available at runtime.
 * 
 * Until the app moves off static export, this serves as the reference
 * implementation. The password validation currently still happens client-side
 * in lambda-functions.tsx and RichTextEditor.tsx.
 * 
 * Migration path:
 * 1. Remove `output: 'export'` from next.config.js (requires server hosting)
 * 2. Or deploy this as a separate Lambda behind API Gateway
 * 3. Frontend calls POST /api/auth/verify-admin { password }
 * 4. Remove NEXT_PUBLIC_PAYMENT_UNLOCK_PASSWORD from .env.local
 * 5. Add ADMIN_UNLOCK_PASSWORD (no NEXT_PUBLIC_ prefix) to server env
 */
import { NextRequest, NextResponse } from 'next/server';

// Server-only — NOT prefixed with NEXT_PUBLIC_, so never shipped to browser.
// Falls back to the legacy NEXT_PUBLIC_ var during migration.
const ADMIN_PASSWORD = process.env.ADMIN_UNLOCK_PASSWORD
  || process.env.NEXT_PUBLIC_PAYMENT_UNLOCK_PASSWORD
  || '';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { password } = body;

    if (!password || typeof password !== 'string') {
      return NextResponse.json({ ok: false, error: 'Password required' }, { status: 400 });
    }

    if (!ADMIN_PASSWORD) {
      return NextResponse.json({ ok: false, error: 'Admin password not configured' }, { status: 500 });
    }

    // Constant-time comparison to prevent timing attacks
    const isValid = password.length === ADMIN_PASSWORD.length
      && timingSafeEqual(password, ADMIN_PASSWORD);

    if (!isValid) {
      return NextResponse.json({ ok: false, error: 'Incorrect password' }, { status: 401 });
    }

    return NextResponse.json({ ok: true });
  } catch {
    return NextResponse.json({ ok: false, error: 'Invalid request' }, { status: 400 });
  }
}

/** Constant-time string comparison (prevents timing attacks). */
function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}
