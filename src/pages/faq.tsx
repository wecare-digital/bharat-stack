/**
 * FAQ Page — Standalone FAQ page with search
 * Uses design token colors consistently
 */

import React from 'react';
import FAQSearch from '../components/FAQSearch';
import { getBrandInfo } from '../utils/faqSearch';

export default function FAQPage() {
  const brand = getBrandInfo();

  return (
    <div style={{ minHeight: '100vh', background: '#f9f9f9', padding: '40px 20px' }}>
      <FAQSearch />

      <div style={{
        maxWidth: '800px',
        margin: '40px auto 0',
        padding: '24px',
        background: 'white',
        borderRadius: '8px',
        textAlign: 'center'
      }}>
        <h3 style={{ marginBottom: '16px', color: '#1a1a1a' }}>Still have questions?</h3>
        <p style={{ marginBottom: '16px', color: '#666' }}>
          We&apos;re here to help! Contact us through any of these channels:
        </p>
        <div style={{ display: 'flex', gap: '12px', justifyContent: 'center', flexWrap: 'wrap' }}>
          <a
            href={`tel:${brand.phone}`}
            style={{ padding: '12px 24px', background: '#1a1a1a', color: 'white', borderRadius: '13px', textDecoration: 'none', fontSize: '14px', minHeight: '44px', display: 'inline-flex', alignItems: 'center' }}
          >
            Call {brand.phone}
          </a>
          <a
            href={`https://wa.me/${brand.whatsapp.replace(/[^0-9]/g, '')}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{ padding: '12px 24px', background: '#059669', color: 'white', borderRadius: '13px', textDecoration: 'none', fontSize: '14px', minHeight: '44px', display: 'inline-flex', alignItems: 'center' }}
          >
            WhatsApp
          </a>
          <a
            href={`mailto:${brand.email}`}
            style={{ padding: '12px 24px', background: '#fff', color: '#1a1a1a', border: '1.5px solid #1a1a1a', borderRadius: '13px', textDecoration: 'none', fontSize: '14px', minHeight: '44px', display: 'inline-flex', alignItems: 'center' }}
          >
            Email
          </a>
        </div>
      </div>
    </div>
  );
}
