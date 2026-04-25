const { BedrockRuntimeClient, InvokeModelCommand } = require('@aws-sdk/client-bedrock-runtime');
const c = new BedrockRuntimeClient({ region: 'us-east-1' });

async function test(name, modelId, body) {
  const start = Date.now();
  try {
    const r = await c.send(new InvokeModelCommand({ modelId, contentType: 'application/json', accept: 'application/json', body: new TextEncoder().encode(JSON.stringify(body)) }));
    const res = JSON.parse(new TextDecoder().decode(r.body));
    const text = res.content?.[0]?.text || res.output?.message?.content?.[0]?.text || '';
    const inTok = res.usage?.input_tokens || res.usage?.inputTokens || 0;
    const outTok = res.usage?.output_tokens || res.usage?.outputTokens || 0;
    console.log(`${name}: OK | ${Date.now()-start}ms | ${inTok}+${outTok} tokens | "${text.substring(0,30)}"`);
    return true;
  } catch (e) {
    console.log(`${name}: FAIL | ${e.name} | ${e.message.substring(0,100)}`);
    return false;
  }
}

async function main() {
  const nova = (sys) => ({ schemaVersion: 'messages-v1', system: [{ text: sys }], messages: [{ role: 'user', content: [{ text: 'Reply with just the word OK' }] }], inferenceConfig: { max_new_tokens: 5 } });
  const claude = (sys) => ({ anthropic_version: 'bedrock-2023-05-31', max_tokens: 5, system: sys, messages: [{ role: 'user', content: 'Reply with just the word OK' }] });

  console.log('=== TESTING ALL BEDROCK MODELS ===\n');
  
  // Amazon Nova family
  await test('nova-pro', 'amazon.nova-pro-v1:0', nova('Reply OK'));
  await test('nova-lite', 'amazon.nova-lite-v1:0', nova('Reply OK'));
  await test('nova-micro', 'amazon.nova-micro-v1:0', nova('Reply OK'));
  
  // Claude - current env model
  await test('claude-opus-4.6', 'us.anthropic.claude-opus-4-6-v1', claude('Reply OK'));
  
  // Claude - latest models
  await test('claude-sonnet-4', 'us.anthropic.claude-sonnet-4-20250514-v1:0', claude('Reply OK'));
  await test('claude-haiku-3.5', 'us.anthropic.claude-3-5-haiku-20241022-v1:0', claude('Reply OK'));
  
  console.log('\n=== DONE ===');
}

const t = setTimeout(() => { console.log('TIMEOUT'); process.exit(0); }, 45000);
main().then(() => { clearTimeout(t); process.exit(0); });
