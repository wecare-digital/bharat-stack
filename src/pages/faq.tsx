/**
 * FAQ Page
 * 
 * Standalone FAQ page with search functionality
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
          We're here to help! Contact us through any of these channels:
        </p>
        <div style={{ display: 'flex', gap: '16px', justifyContent: 'center', flexWrap: 'wrap' }}>
          <a 
            href={`tel:${brand.phone}`}
            style={{
              padding: '12px 24px',
              background: '#4CAF50',
              color: 'white',
              borderRadius: '8px',
              textDecoration: 'none',
              fontSize: '14px'
            }}
          >
            📞 Call {brand.phone}
          </a>
          <a 
            href={`https://wa.me/${brand.whatsapp.replace(/[^0-9]/g, '')}`}
            target="_blank"
            rel="noopener noreferrer"
            style={{
              padding: '12px 24px',
              background: '#25D366',
              color: 'white',
              borderRadius: '8px',
              textDecoration: 'none',
              fontSize: '14px'
            }}
          >
            💬 WhatsApp
          </a>
          <a 
            href={`mailto:${brand.email}`}
            style={{
              padding: '12px 24px',
              background: '#2196F3',
              color: 'white',
              borderRadius: '8px',
              textDecoration: 'none',
              fontSize: '14px'
            }}
          >
            ✉️ Email
          </a>
        </div>
      </div>
    </div>
  );
}
