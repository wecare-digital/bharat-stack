import { createHash, createPublicKey, timingSafeEqual, verify } from 'node:crypto';

/** Verify Wix PSP Digest JWT against an operator-pinned public key.
 * The raw body must be captured before JSON parsing. Never load a key from JWT headers.
 * Authentication does not replace durable transaction/refund idempotency.
 */
export function verifyWixRequest({ digest, rawBody, publicKey, now = Math.floor(Date.now() / 1000) }) {
  try {
    if (!Buffer.isBuffer(rawBody) || rawBody.length > 1048576 || !Number.isSafeInteger(now)) throw Error();
    if (typeof digest !== 'string' || !digest.startsWith('JWT=') || digest.length > 16384) throw Error();
    const parts = digest.slice(4).split('.');
    if (parts.length !== 3 || parts.some(p => !/^[A-Za-z0-9_-]+$/.test(p))) throw Error();
    const decode = p => {
      const b = Buffer.from(p, 'base64url');
      if (b.toString('base64url') !== p) throw Error();
      return b;
    };
    const header = JSON.parse(decode(parts[0]).toString('utf8'));
    if (header.alg !== 'RS256' || header.crit !== undefined || header.b64 !== undefined) throw Error();
    const key = createPublicKey(publicKey);
    if (key.asymmetricKeyType !== 'rsa') throw Error();
    if (!verify('RSA-SHA256', Buffer.from(`${parts[0]}.${parts[1]}`, 'ascii'), key, decode(parts[2]))) throw Error();
    const claims = JSON.parse(decode(parts[1]).toString('utf8'));
    if (!Number.isSafeInteger(claims.iat) || !Number.isSafeInteger(claims.exp)
        || claims.iat > now || claims.exp <= now || claims.exp <= claims.iat) throw Error();
    if (claims.nbf !== undefined && (!Number.isSafeInteger(claims.nbf) || claims.nbf > now)) throw Error();
    const expected = claims.data?.SHA256;
    if (typeof expected !== 'string' || !/^[a-fA-F0-9]{64}$/.test(expected)) throw Error();
    const actual = createHash('sha256').update(rawBody).digest();
    if (!timingSafeEqual(actual, Buffer.from(expected, 'hex'))) throw Error();
    return true;
  } catch {
    throw new Error('Invalid Wix PSP request');
  }
}
