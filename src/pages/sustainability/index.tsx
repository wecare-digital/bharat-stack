/**
 * Sustainability Page - Coming Soon
 * URL: https://stack.wecare.digital/sustainability
 */
import React from 'react';
import Head from 'next/head';

const SustainabilityPage: React.FC = () => (
  <>
    <Head>
      <title>Sustainability | WECARE.DIGITAL</title>
      <meta name="description" content="Sustainability by WECARE.DIGITAL — coming soon." />
      <link rel="canonical" href="https://stack.wecare.digital/sustainability" />
    </Head>
    <div style={{ minHeight: 'calc(100vh - 96px - 69px)', display: 'flex', alignItems: 'center', justifyContent: 'center', paddingTop: 96 }}>
      <div style={{ textAlign: 'center' }}>
        <h1 style={{ fontSize: 42, fontWeight: 700, color: '#1a1a1a', margin: '0 0 12px', letterSpacing: -1 }}>Sustainability</h1>
        <p style={{ fontSize: 21, color: '#6b7280', margin: 0 }}>Coming soon</p>
      </div>
    </div>
  </>
);

export default SustainabilityPage;
