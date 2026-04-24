#!/usr/bin/env node
/**
 * One-time script to update AWS Secrets Manager with new Wix API key.
 * Run: node scripts/_update_aws_secret.mjs
 */
import { readFileSync } from 'fs';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { execSync } from 'child_process';

const dir = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const env = readFileSync(resolve(dir, '.env.local'), 'utf8');
const keyMatch = env.match(/^WIX_API_KEY=(.+)$/m);
if (!keyMatch) { console.error('No WIX_API_KEY in .env.local'); process.exit(1); }
const key = keyMatch[1].trim();
console.log(`Key length: ${key.length}, ends: ...${key.slice(-4)}`);

const secretValue = JSON.stringify({ api_key: key, site_id: 'd3ed75eb-e0b7-45c2-a743-f83cfa19379a' });

try {
  console.log('Updating AWS Secrets Manager...');
  const result = execSync(
    `aws secretsmanager put-secret-value --secret-id "wecare/wix-api-key" --secret-string '${secretValue.replace(/'/g, "'\\''")}' --region us-east-1 --output json --no-cli-pager`,
    { encoding: 'utf8', timeout: 60000 }
  );
  console.log('✅ AWS Secrets Manager updated');
  console.log(result.substring(0, 200));
} catch (e) {
  console.error('❌ Failed:', e.message);
  console.log('\nManual command:');
  console.log(`aws secretsmanager put-secret-value --secret-id "wecare/wix-api-key" --secret-string '${secretValue}' --region us-east-1`);
}
