'use client';

import { useState } from 'react';

export default function TestAgentPage() {
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);

  const testAPI = async () => {
    setLoading(true);
    setResult('Testing...');
    
    try {
      const response = await fetch('/api/ai/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          messageContent: 'help',
          context: 'internal-admin',
          sessionId: `test-${Date.now()}`,
        }),
      });

      const data = await response.json();
      setResult(JSON.stringify(data, null, 2));
    } catch (error: any) {
      setResult(`Error: ${error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ padding: '40px', maxWidth: '800px', margin: '0 auto' }}>
      <h1>Floating Agent API Test</h1>
      <p>Test the internal API route</p>
      
      <button 
        onClick={testAPI} 
        disabled={loading}
        style={{
          padding: '12px 24px',
          background: '#059669',
          color: 'white',
          border: 'none',
          borderRadius: '6px',
          cursor: loading ? 'not-allowed' : 'pointer',
          fontSize: '16px',
          marginTop: '20px',
        }}
      >
        {loading ? 'Testing...' : 'Test API Route'}
      </button>

      {result && (
        <pre style={{
          marginTop: '20px',
          padding: '20px',
          background: '#f5f5f5',
          borderRadius: '8px',
          overflow: 'auto',
          maxHeight: '400px',
        }}>
          {result}
        </pre>
      )}
    </div>
  );
}
