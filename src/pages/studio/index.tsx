/**
 * Studio Page - Coming Soon
 * URL: https://stack.wecare.digital/studio
 */
import React from 'react';
import Head from 'next/head';

const StudioPage: React.FC = () => (
  <>
    <Head>
      <title>Studio | Bharat Stack by WECARE.DIGITAL</title>
      <meta name="description" content="Studio by WECARE.DIGITAL — coming soon." />
      <link rel="canonical" href="https://stack.wecare.digital/studio" />
    </Head>
    <div style={{ minHeight: 'calc(100vh - 96px - 69px)', display: 'flex', alignItems: 'center', justifyContent: 'center', paddingTop: 96 }}>
      <div style={{ textAlign: 'center' }}>
        <h1 style={{ fontSize: 42, fontWeight: 700, color: '#1a1a1a', margin: '0 0 12px', letterSpacing: -1 }}>Studio</h1>
        <p style={{ fontSize: 21, color: '#6b7280', margin: 0 }}>Coming soon</p>
      </div>
    </div>
  </>
);

export default StudioPage;
