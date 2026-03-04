import { NextRequest, NextResponse } from 'next/server';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://api.wecare.digital';
const TIMEOUT_MS = 30000; // 30 second timeout

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    console.log('[API Proxy] Request:', {
      messageContent: body.messageContent?.substring(0, 100),
      context: body.context,
      sessionId: body.sessionId,
    });

    // Forward request to API Gateway with timeout
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TIMEOUT_MS);

    let response: Response;
    try {
      response = await fetch(`${API_BASE}/ai/generate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
    } catch (fetchErr: any) {
      clearTimeout(timeoutId);
      if (fetchErr.name === 'AbortError') {
        console.error('[API Proxy] Request timed out after', TIMEOUT_MS, 'ms');
        return NextResponse.json(
          { suggestedResponse: 'Request timed out. The server took too long to respond. Please try again.' },
          { status: 504 }
        );
      }
      throw fetchErr;
    }
    clearTimeout(timeoutId);

    const rawData = await response.json();

    console.log('[API Proxy] Raw response status:', response.status, 'keys:', Object.keys(rawData));

    // Normalize: API Gateway wraps Lambda output as { statusCode, headers, body }
    // We need to unwrap and return a flat { suggestedResponse, error?, sessionId? }
    let result: Record<string, any> = {};

    if (rawData.body) {
      // API Gateway format — body is a JSON string (or already parsed object)
      try {
        const parsed = typeof rawData.body === 'string' ? JSON.parse(rawData.body) : rawData.body;
        result = parsed;
      } catch {
        // body wasn't valid JSON, treat as plain text
        result = { suggestedResponse: String(rawData.body) };
      }
    } else if (rawData.suggestedResponse || rawData.suggestion) {
      // Direct Lambda response (no API Gateway wrapping)
      result = rawData;
    } else if (rawData.error) {
      // Error-only response
      result = rawData;
    } else {
      // Unknown format — pass through
      result = rawData;
    }

    // Normalize response field name: always use suggestedResponse
    if (result.suggestion && !result.suggestedResponse) {
      result.suggestedResponse = result.suggestion;
      delete result.suggestion;
    }

    // If there's an error field alongside suggestedResponse, log it but still return the response
    if (result.error) {
      console.error('[API Proxy] Backend error:', result.error);
    }

    console.log('[API Proxy] Normalized response:', {
      hasSuggestedResponse: !!result.suggestedResponse,
      hasError: !!result.error,
      sessionId: result.sessionId,
    });

    return NextResponse.json(result, { status: 200 });
  } catch (error: any) {
    console.error('[API Proxy] Exception:', error?.message || error);
    return NextResponse.json(
      {
        suggestedResponse: 'Connection error. Please check your network and try again.',
        error: error?.message || 'Unknown error',
      },
      { status: 500 }
    );
  }
}
