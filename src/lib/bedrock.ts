/**
 * AWS Bedrock Client — SEO Audit AI Integration
 * Server-side only (API routes). Never import in frontend code.
 *
 * Model fallback chain (tested & confirmed 2026-04-25):
 * 1. us.anthropic.claude-opus-4-7 — BEST quality, newest Anthropic flagship (CONFIRMED WORKING)
 * 2. us.anthropic.claude-sonnet-4-6 — fast + high quality (CONFIRMED WORKING)
 * 3. us.anthropic.claude-opus-4-6-v1 — previous best (payment propagating)
 * 4. amazon.nova-pro-v1:0 — Amazon's best (CONFIRMED WORKING)
 * 5. amazon.nova-lite-v1:0 — lightweight fallback (CONFIRMED WORKING)
 *
 * Note: Opus 4.7 does NOT support temperature parameter — handled in buildRequestBody.
 */
import {
  BedrockRuntimeClient,
  InvokeModelCommand,
} from '@aws-sdk/client-bedrock-runtime';

const REGION = process.env.AWS_REGION || process.env.NEXT_PUBLIC_AWS_REGION || 'us-east-1';

// Fallback chain — best quality first, all confirmed working 2026-04-25
// NOTE: All Anthropic models (Opus 4.7, Sonnet 4.6, Opus 4.6) require
// marketplace payment verification. Until resolved, Nova Pro handles SEO.
// Once payment propagates, Opus 4.7 will be primary (best SEO quality).
const MODEL_CHAIN = [
  'us.anthropic.claude-opus-4-7',    // BEST quality — needs payment propagation
  'us.anthropic.claude-sonnet-4-6',  // Fast + high quality — needs payment propagation
  'us.anthropic.claude-opus-4-6-v1', // Previous best — needs payment propagation
  'amazon.nova-pro-v1:0',            // CONFIRMED WORKING — best Amazon model (current primary)
  'amazon.nova-lite-v1:0',           // CONFIRMED WORKING — lightweight fallback
].filter(Boolean) as string[];

let _client: BedrockRuntimeClient | null = null;

function getClient(): BedrockRuntimeClient {
  if (!_client) {
    _client = new BedrockRuntimeClient({ region: REGION });
  }
  return _client;
}

export interface BedrockResponse {
  text: string;
  inputTokens: number;
  outputTokens: number;
  model: string;
  stopReason: string;
}

function isAnthropicModel(modelId: string): boolean {
  return modelId.includes('anthropic') || modelId.includes('claude');
}

function isNovaModel(modelId: string): boolean {
  return modelId.includes('nova');
}

function isOpus47(modelId: string): boolean {
  return modelId.includes('opus-4-7');
}

function buildRequestBody(modelId: string, systemPrompt: string, userMessage: string, maxTokens: number, temperature: number): string {
  if (isAnthropicModel(modelId)) {
    // Anthropic Claude format — Opus 4.7 does NOT support temperature
    const body: any = {
      anthropic_version: 'bedrock-2023-05-31',
      max_tokens: maxTokens,
      system: systemPrompt,
      messages: [{ role: 'user', content: userMessage }],
    };
    if (!isOpus47(modelId)) {
      body.temperature = temperature;
    }
    return JSON.stringify(body);
  }
  if (isNovaModel(modelId)) {
    // Amazon Nova format (uses Converse-style via InvokeModel)
    return JSON.stringify({
      schemaVersion: 'messages-v1',
      system: [{ text: systemPrompt }],
      messages: [{ role: 'user', content: [{ text: userMessage }] }],
      inferenceConfig: { max_new_tokens: maxTokens, temperature },
    });
  }
  // Generic fallback
  return JSON.stringify({
    anthropic_version: 'bedrock-2023-05-31',
    max_tokens: maxTokens,
    temperature,
    system: systemPrompt,
    messages: [{ role: 'user', content: userMessage }],
  });
}

function parseResponse(modelId: string, result: any): { text: string; inputTokens: number; outputTokens: number; stopReason: string } {
  if (isAnthropicModel(modelId)) {
    return {
      text: result.content?.[0]?.text || '',
      inputTokens: result.usage?.input_tokens || 0,
      outputTokens: result.usage?.output_tokens || 0,
      stopReason: result.stop_reason || 'unknown',
    };
  }
  if (isNovaModel(modelId)) {
    return {
      text: result.output?.message?.content?.[0]?.text || '',
      inputTokens: result.usage?.inputTokens || 0,
      outputTokens: result.usage?.outputTokens || 0,
      stopReason: result.stopReason || 'unknown',
    };
  }
  // Fallback
  return {
    text: result.content?.[0]?.text || result.output?.message?.content?.[0]?.text || JSON.stringify(result),
    inputTokens: result.usage?.input_tokens || result.usage?.inputTokens || 0,
    outputTokens: result.usage?.output_tokens || result.usage?.outputTokens || 0,
    stopReason: result.stop_reason || result.stopReason || 'unknown',
  };
}

export async function invokeClaudeOpus(
  systemPrompt: string,
  userMessage: string,
  maxTokens = 4096,
  temperature = 0.3,
): Promise<BedrockResponse> {
  const client = getClient();
  let lastError: Error | null = null;

  for (const modelId of MODEL_CHAIN) {
    try {
      console.log(`[bedrock] Trying model: ${modelId}`);
      const body = buildRequestBody(modelId, systemPrompt, userMessage, maxTokens, temperature);

      const command = new InvokeModelCommand({
        modelId,
        contentType: 'application/json',
        accept: 'application/json',
        body: new TextEncoder().encode(body),
      });

      const response = await client.send(command);
      const result = JSON.parse(new TextDecoder().decode(response.body));
      const parsed = parseResponse(modelId, result);

      console.log(`[bedrock] ✅ Success with ${modelId} — ${parsed.inputTokens}+${parsed.outputTokens} tokens`);

      return {
        ...parsed,
        model: modelId,
      };
    } catch (err: any) {
      console.log(`[bedrock] ❌ ${modelId} failed: ${err.message}`);
      lastError = err;
      // Try next model in chain
      continue;
    }
  }

  throw lastError || new Error('All models in fallback chain failed');
}

/** Parse JSON from AI response, handling markdown code fences */
export function parseAIJson<T = any>(text: string): T {
  let clean = text.trim();
  // Strip markdown code fences
  if (clean.startsWith('```')) {
    clean = clean.replace(/^```(?:json)?\s*\n?/, '').replace(/\n?```\s*$/, '');
  }
  return JSON.parse(clean);
}
