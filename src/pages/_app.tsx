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
import { Authenticator, ThemeProvider, Theme } from '@aws-amplify/ui-react';
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

// Custom Amplify UI Theme - Black buttons with 13px border radius
const authTheme: Theme = {
  name: 'base-crm-theme',
  tokens: {
    colors: {
      brand: {
        primary: {
          10: { value: '#f5f5f5' },
          20: { value: '#e5e5e5' },
          40: { value: '#a3a3a3' },
          60: { value: '#525252' },
          80: { value: '#1a1a1a' },
          90: { value: '#0a0a0a' },
          100: { value: '#000000' },
        },
      },
      font: {
        interactive: { value: '#1a1a1a' },
      },
      background: {
        primary: { value: '#ffffff' },
        secondary: { value: '#f9fafb' },
      },
    },
    components: {
      authenticator: {
        router: {
          borderWidth: { value: '0' },
          boxShadow: { value: '0 4px 24px rgba(0, 0, 0, 0.08)' },
        },
      },
      button: {
        primary: {
          backgroundColor: { value: '#1a1a1a' },
          color: { value: '#ffffff' },
          borderRadius: { value: '13px' },
          _hover: {
            backgroundColor: { value: '#333333' },
          },
          _active: {
            backgroundColor: { value: '#000000' },
          },
        },
        link: {
          color: { value: '#1a1a1a' },
          _hover: {
            color: { value: '#525252' },
            backgroundColor: { value: 'transparent' },
          },
        },
      },
      fieldcontrol: {
        borderRadius: { value: '10px' },
        borderColor: { value: '#e5e7eb' },
        _focus: {
          borderColor: { value: '#1a1a1a' },
          boxShadow: { value: '0 0 0 2px rgba(26, 26, 26, 0.1)' },
        },
      },
      tabs: {
        item: {
          color: { value: '#6b7280' },
          _active: {
            color: { value: '#1a1a1a' },
            borderColor: { value: '#1a1a1a' },
          },
          _hover: {
            color: { value: '#1a1a1a' },
          },
        },
      },
    },
    radii: {
      small: { value: '10px' },
      medium: { value: '13px' },
      large: { value: '16px' },
    },
    space: {
      small: { value: '0.75rem' },
      medium: { value: '1rem' },
      large: { value: '1.5rem' },
    },
    fontSizes: {
      small: { value: '0.875rem' },
      medium: { value: '1rem' },
      large: { value: '1.125rem' },
    },
  },
};

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
  <div style={{ textAlign: 'center', padding: '24px 20px' }}>
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '7px' }}>
      <img 
        src="https://auth.wecare.digital/stream/media/m/wecare-digital.png" 
        alt="Base CRM" 
        style={{ width: '52px', height: '52px', borderRadius: '10px' }}
        onError={(e) => { (e.target as HTMLImageElement).src = FAVICON_URL; }}
      />
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'center', textAlign: 'left', height: '52px' }}>
        <span style={{ fontSize: '24px', fontWeight: 800, color: '#1a1a1a', letterSpacing: '-0.3px', lineHeight: 1 }}>Base CRM</span>
        <span style={{ fontSize: '13px', fontWeight: 600, color: '#6b7280', lineHeight: 1, marginTop: '4px' }}>by WECARE.DIGITAL</span>
      </div>
    </div>
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
      <ThemeProvider theme={authTheme}>
        <Authenticator hideSignUp={true} components={{ Header: AuthHeader }}>
          {({ signOut, user }) => (
            <>
              <Component {...pageProps} signOut={() => { signOut?.(); router.push('/'); }} user={user} />
              <FloatingAgent />
            </>
          )}
        </Authenticator>
      </ThemeProvider>
    </ErrorBoundary>
  );
}
