#!/usr/bin/env node
/**
 * Explicit Wix Headless credential loader.
 *
 * This script intentionally contains no site ID, account ID, secret name, or key.
 * Populate all four values in .env.local only when provisioning the NEW Headless
 * project, then run this script.
 */
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { execFileSync } from 'child_process';

const dir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const env = readFileSync(resolve(dir, '.env.local'), 'utf8');

function required(name) {
  const match = env.match(new RegExp(`^${name}=(.+)$`, 'm'));
  const value = match?.[1]?.trim();
  if (!value) {
    console.error(`Missing ${name} in .env.local`);
    process.exit(1);
  }
  return value;
}

const key = required('WIX_API_KEY');
const siteId = required('WIX_SITE_ID');
const accountId = required('WIX_ACCOUNT_ID');
const secretName = required('WIX_API_KEY_SECRET');

const secretValue = JSON.stringify({
  api_key: key,
  site_id: siteId,
  account_id: accountId,
});

execFileSync(
  'aws',
  [
    'secretsmanager',
    'put-secret-value',
    '--secret-id',
    secretName,
    '--secret-string',
    secretValue,
    '--region',
    'us-east-1',
    '--output',
    'json',
    '--no-cli-pager',
  ],
  { stdio: 'ignore', timeout: 60000 }
);

console.log('Wix Headless credentials updated in AWS Secrets Manager.');
