/**
 * Base CRM by WECARE.DIGITAL
 * Simplified auth - just wrap protected pages with Authenticator
 */

import type { AppProps } from 'next/app';
import Head from 'next/head';
import Script from 'next/script';
import { useRouter } from 'next/router';
import { useState, useEffect } from 'react';
import { Amplify } from 'aws-amplify';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';
import '../styles/Pages.css';
import '../styles/Layout.css';
import '../styles/Dashboard.css';
import FloatingAgent from '../components/FloatingAgent';
import ErrorBoundary from '../components/ErrorBoundary';

// Configure Amplify
Amplify.configure({
  Auth: {
    Cognito: {
      userPoolId: 'us-east-1_CC9u1fYh6',
      userPoolClientId: '5na5ba2pbpanm36138jdcd9gck',
      identityPoolId: 'us-east-1:ef6b783a-f0c5-4d2f-925d-9460e6a733ce',
      loginWith: {
        oauth: {
          domain: 'sso.wecare.digital',
          scopes: ['openid', 'email', 'profile'],
          redirectSignIn: ['https://base.wecare.digital/', 'http://localhost:3000/'],
          redirectSignOut: ['https://base.wecare.digital/', 'http://localhost:3000/'],
          responseType: 'code' as const
        },
        username: true,
        email: true
      }
    }
  }
});

const LOGO_URL = 'https://auth.wecare.digital/stream/media/m/wecare-digital.png';
const LOGO_SVG_URL = 'https://auth.wecare.digital/stream/media/m/wecare-digital.svg';
const FAVICON_URL = 'https://auth.wecare.digital/stream/media/m/wecare-digital.ico';
const GA_MEASUREMENT_ID = 'G-S3G6REP6Q7';

// Structured data for the organization
const organizationSchema = {
  "@context": "https://schema.org",
  "@type": "Organization",
  "name": "WECARE.DIGITAL",
  "url": "https://wecare.digital",
  "logo": LOGO_URL,
  "sameAs": [],
  "contactPoint": {
    "@type": "ContactPoint",
    "contactType": "customer service",
    "url": "https://www.wecare.digital/contact"
  }
};

// Structured data for the software application
const softwareSchema = {
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Base CRM by WECARE.DIGITAL",
  "applicationCategory": "BusinessApplication",
  "operatingSystem": "Web",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "INR"
  },
  "description": "Multi-channel messaging CRM platform with WhatsApp Business API, SMS, Email, and Voice integration.",
  "publisher": {
    "@type": "Organization",
    "name": "WECARE.DIGITAL"
  }
};

// Structured data for the website
const websiteSchema = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  "name": "Base CRM by WECARE.DIGITAL",
  "url": "https://base.wecare.digital",
  "potentialAction": {
    "@type": "SearchAction",
    "target": "https://base.wecare.digital/search?q={search_term_string}",
    "query-input": "required name=search_term_string"
  }
};

// Breadcrumb schema for internal pages
const getBreadcrumbSchema = (pageName: string, pageUrl: string) => ({
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "name": "Home",
      "item": "https://base.wecare.digital"
    },
    {
      "@type": "ListItem",
      "position": 2,
      "name": pageName,
      "item": pageUrl
    }
  ]
});

const AuthHeader = () => (
  <div style={{ textAlign: 'center', padding: '20px' }}>
    <img src={LOGO_URL} alt="Base CRM" style={{ width: '64px', height: '64px', borderRadius: '12px', marginBottom: '12px' }} />
    <h1 style={{ fontSize: '24px', fontWeight: 700, color: '#1a1a1a', margin: '0 0 4px' }}>Base CRM</h1>
    <p style={{ color: '#6b7280', fontSize: '14px', margin: 0 }}>by WECARE.DIGITAL</p>
  </div>
);

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();
  const [mounted, setMounted] = useState(false);
  
  const isPublic = router.pathname === '/';

  useEffect(() => {
    setMounted(true);
  }, []);

  // Wait for client-side mount
  if (!mounted) {
    return null;
  }

  // Public page
  if (isPublic) {
    return (
      <ErrorBoundary>
        <Head>
          <title>Base CRM by WECARE.DIGITAL - WhatsApp Business API Platform</title>
          <meta name="description" content="Multi-channel messaging CRM platform. Connect with customers on WhatsApp, SMS, Email, and Voice." />
          <meta name="viewport" content="width=device-width, initial-scale=1" />
          <link rel="icon" href={FAVICON_URL} />
          <link rel="apple-touch-icon" href={LOGO_URL} />
          <meta property="og:title" content="Base CRM by WECARE.DIGITAL" />
          <meta property="og:description" content="Multi-channel messaging CRM platform with WhatsApp Business API integration." />
          <meta property="og:image" content={LOGO_URL} />
          <meta property="og:url" content="https://base.wecare.digital" />
          <meta property="og:type" content="website" />
          <meta name="twitter:card" content="summary_large_image" />
          <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationSchema) }} />
          <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(softwareSchema) }} />
          <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(websiteSchema) }} />
        </Head>
        {/* Google Analytics & Ads */}
        <Script src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`} strategy="afterInteractive" />
        <Script id="google-analytics-ads" strategy="afterInteractive">
          {`
            window.dataLayer = window.dataLayer || [];
            function gtag(){dataLayer.push(arguments);}
            gtag('js', new Date());
            gtag('config', '${GA_MEASUREMENT_ID}');
            gtag('config', '${GA_MEASUREMENT_ID}', { 'send_page_view': true });
          `}
        </Script>
        <Component {...pageProps} />
      </ErrorBoundary>
    );
  }

  // Get page name for breadcrumb
  const pageName = router.pathname.split('/').filter(Boolean).map(s => s.charAt(0).toUpperCase() + s.slice(1)).join(' > ') || 'Dashboard';
  const pageUrl = `https://base.wecare.digital${router.pathname}`;

  // Protected pages
  return (
    <ErrorBoundary>
      <Head>
        <title>Base CRM by WECARE.DIGITAL</title>
        <meta name="description" content="Base CRM Dashboard - Multi-channel messaging platform" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link rel="icon" href={FAVICON_URL} />
        <link rel="apple-touch-icon" href={LOGO_URL} />
        <meta name="robots" content="noindex, nofollow" />
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(organizationSchema) }} />
        <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(getBreadcrumbSchema(pageName, pageUrl)) }} />
      </Head>
      {/* Google Analytics & Ads */}
      <Script src={`https://www.googletagmanager.com/gtag/js?id=${GA_MEASUREMENT_ID}`} strategy="afterInteractive" />
      <Script id="google-analytics-ads" strategy="afterInteractive">
        {`
          window.dataLayer = window.dataLayer || [];
          function gtag(){dataLayer.push(arguments);}
          gtag('js', new Date());
          gtag('config', '${GA_MEASUREMENT_ID}');
          gtag('config', '${GA_MEASUREMENT_ID}', { 'send_page_view': true });
        `}
      </Script>
      <Authenticator hideSignUp={true} components={{ Header: AuthHeader }}>
        {({ signOut, user }) => (
          <>
            <Component {...pageProps} signOut={() => { signOut?.(); router.push('/'); }} user={user} />
            <FloatingAgent />
          </>
        )}
      </Authenticator>
    </ErrorBoundary>
  );
}
