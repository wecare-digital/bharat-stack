/**
 * AWS Bedrock Client — SEO Audit AI Integration
 * Server-side only (API routes). Never import in frontend code.
 *
 * Model fallback chain (tested 2026-04-25):
 * 1. BEDROCK_MODEL_ID from env (user's choice — claude-opus-4-6, requires marketplace agreement)
 * 2. amazon.nova-pro-v1:0 (Amazon's own model, CONFIRMED WORKING)
 * 3. amazon.nova-lite-v1:0 (lighter fallback, CONFIRMED WORKING)
 *
 * Claude models status:
 * - anthropic.claude-opus-4-6-v1: Requires marketplace agreement + valid payment method
 * - us.anthropic.claude-3-5-sonnet-20241022-v2:0: end-of-life
 * - us.anthropic.claude-sonnet-4-*: Legacy
 * - us.anthropic.claude-3-5-haiku-*: Legacy
 *
 * To enable Claude Opus 4.6:
 * 1. Fix payment method: AWS Console > Billing > Payment preferences
 * 2. Accept agreement: aws bedrock create-foundation-model-agreement --model-id anthropic.claude-opus-4-6-v1 --offer-token <token> --region us-east-1
 * 3. Verify: aws bedrock get-foundation-model --model-identifier anthropic.claude-opus-4-6-v1 --region us-east-1
 */
import {
  BedrockRuntimeClient,
  InvokeModelCommand,
} from '@aws-sdk/client-bedrock-runtime';

const REGION = process.env.AWS_REGION || process.env.NEXT_PUBLIC_AWS_REGION || 'us-east-1';

// Fallback chain — only models confirmed working as of 2026-04-25
const MODEL_CHAIN = [
  process.env.BEDROCK_MODEL_ID,  // anthropic.claude-opus-4-6-v1 (needs marketplace agreement)
  'amazon.nova-pro-v1:0',        // CONFIRMED WORKING — best quality Amazon model
  'amazon.nova-lite-v1:0',       // CONFIRMED WORKING — lighter fallback
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

function buildRequestBody(modelId: string, systemPrompt: string, userMessage: string, maxTokens: number, temperature: number): string {
  if (isAnthropicModel(modelId)) {
    // Anthropic Claude format
    return JSON.stringify({
      anthropic_version: 'bedrock-2023-05-31',
      max_tokens: maxTokens,
      temperature,
      system: systemPrompt,
      messages: [{ role: 'user', content: userMessage }],
    });
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
