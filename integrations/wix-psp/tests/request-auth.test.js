import test from 'node:test';
import assert from 'node:assert/strict';
import { createHash, generateKeyPairSync, sign } from 'node:crypto';
import { verifyWixRequest } from '../request-auth.js';
const pair = generateKeyPairSync('rsa', { modulusLength: 2048 });
const publicKey = pair.publicKey.export({ type: 'spki', format: 'pem' });
const rawBody = Buffer.from('{ "amount": "100" }');
const now = 2000000000;
function token(overrides = {}, header = { alg: 'RS256' }, privateKey = pair.privateKey) {
  const claims = { iat: now - 5, exp: now + 60, data: { SHA256: createHash('sha256').update(rawBody).digest('hex') }, ...overrides };
  const encoded = [header, claims].map(v => Buffer.from(JSON.stringify(v)).toString('base64url')).join('.');
  return `JWT=${encoded}.${sign('RSA-SHA256', Buffer.from(encoded), privateKey).toString('base64url')}`;
}
function check(digest = token(), body = rawBody) { return verifyWixRequest({ digest, rawBody: body, publicKey, now }); }
test('accepts signed body', () => assert.equal(check(), true));
test('rejects changed whitespace in raw body', () => assert.throws(() => check(token(), Buffer.from('{"amount":"100"}'))));
test('rejects tampered signature', () => { const t = token(); assert.throws(() => check(t.slice(0, -8) + 'AAAAAAAA')); });
test('rejects another RSA key', () => assert.throws(() => check(token({}, { alg: 'RS256' }, generateKeyPairSync('rsa', { modulusLength: 2048 }).privateKey))));
for (const [name, claims] of Object.entries({ expired: { exp: now }, future: { iat: now + 1 }, missingExpiry: { exp: null }, invalidDigest: { data: { SHA256: 'zz' } }, notYetValid: { nbf: now + 1 } })) {
  test(`rejects ${name}`, () => assert.throws(() => check(token(claims))));
}
for (const header of [{ alg: 'none' }, { alg: 'HS256' }, { alg: 'RS256', crit: ['unknown'] }, { alg: 'RS256', b64: false }]) {
  test(`rejects header ${JSON.stringify(header)}`, () => assert.throws(() => check(token({}, header))));
}
test('rejects unparsed non-byte body', () => assert.throws(() => check(token(), rawBody.toString())));
test('rejects oversized body', () => assert.throws(() => check(token(), Buffer.alloc(1048577))));
test('rejects missing Digest prefix', () => assert.throws(() => check(token().slice(4))));
